
"""
rl_manager.py - Reinforcement Learning Manager for Multi-Stream Download Optimization
Implements Q-Learning aligned with the paper's approach (Section 3)
"""
import json
import time
import random
import os
from collections import deque
from config import *


class RLConnectionManager:
    """
    Q-Learning agent for optimizing parallel TCP stream count.
    Implements the approach from Section 3 of the paper.
    """
    
    def __init__(self, 
                 learning_rate=RL_LEARNING_RATE, 
                 discount_factor=RL_DISCOUNT_FACTOR, 
                 exploration_rate=RL_EXPLORATION_RATE):
        # RL parameters
        self.learning_rate = learning_rate  # α
        self.discount_factor = discount_factor  # γ
        self.exploration_rate = exploration_rate  # ε
        self.min_exploration_rate = RL_MIN_EXPLORATION
        self.exploration_decay = RL_EXPLORATION_DECAY
        
        # Q-table: Q[state][action] = value
        self.Q = {}
        
        # Connection management
        self.current_connections = DEFAULT_NUM_STREAMS
        self.max_connections = MAX_STREAMS
        self.min_connections = MIN_STREAMS
        
        # Monitoring interval tracking (paper's MI concept)
        self.last_decision_time = time.time()
        self.monitoring_interval = RL_MONITORING_INTERVAL
        
        # State tracking for learning
        self.last_state = None
        self.last_action = None
        self.last_metrics = None  # Store metrics from previous MI
        
        # Performance tracking
        self.metrics_history = deque(maxlen=50)
        self.total_decisions = 0
        self.total_learning_updates = 0
        
        self.performance_stats = {
            'successful_adjustments': 0,
            'total_positive_rewards': 0,
            'total_negative_rewards': 0,
            'average_reward': 0,
            'convergence_episodes': 0
        }
        
        # Load existing Q-table if available
        self.load_q_table()
        
        if ENABLE_VERBOSE_LOGGING:
            print("✅ RL Manager initialized")
            print(f"   Learning Rate: {self.learning_rate}")
            print(f"   Discount Factor: {self.discount_factor}")
            print(f"   Exploration Rate: {self.exploration_rate}")
            print(f"   Q-table size: {len(self.Q)} states")

    # ==================== State Representation (Section 3.1.1) ====================
    
    def discretize_state(self, throughput, rtt, packet_loss):
        """
        Simplified state discretization for faster convergence.
        Paper uses: (RTT gradient, RTT ratio, plr, avg throughput)
        We simplify to: (throughput_level, rtt_level, loss_level)
        
        Total states: 3 × 3 × 2 = 18 (manageable for Q-learning)
        """
        # Discretize throughput (Mbps)
        if throughput < 5:
            throughput_level = 0  # Low
        elif throughput < 25:
            throughput_level = 1  # Medium
        else:
            throughput_level = 2  # High

        # Discretize RTT (milliseconds)
        if rtt < 100:
            rtt_level = 0  # Good
        elif rtt < 300:
            rtt_level = 1  # Fair
        else:
            rtt_level = 2  # Poor

        # Discretize packet loss (as percentage)
        if packet_loss < 1.0:
            loss_level = 0  # Low
        else:
            loss_level = 1  # High

        return (throughput_level, rtt_level, loss_level)

    # ==================== Action Selection (Section 3.1.2) ====================
    
    def get_available_actions(self):
        """
        Available actions for adjusting stream count.
        Paper uses: aggressive increase, conservative increase, no change,
                   conservative decrease, aggressive decrease
        """
        return {
            0: 3,    # Aggressive Increase (+3 streams)
            1: 1,    # Conservative Increase (+1 stream)
            2: 0,    # No Change
            3: -1,   # Conservative Decrease (-1 stream)
            4: -3    # Aggressive Decrease (-3 streams)
        }
    
    def get_q_value(self, state, action):
        """Get Q-value with proper initialization."""
        if state not in self.Q:
            # Initialize all actions for new state
            self.Q[state] = {a: 0.0 for a in range(5)}
        return self.Q[state].get(action, 0.0)
    
    def choose_action(self, state):
        """
        ε-greedy action selection with decay.
        Balances exploration and exploitation.
        """
        # Gradual exploration decay
        self.exploration_rate = max(
            self.min_exploration_rate,
            self.exploration_rate * self.exploration_decay
        )
        
        # Exploration: random action
        if random.random() < self.exploration_rate:
            return random.randint(0, 4)
        
        # Exploitation: best known action
        if state not in self.Q:
            self.Q[state] = {a: 0.0 for a in range(5)}
        
        q_values = self.Q[state]
        max_q = max(q_values.values())
        
        # Handle ties by random selection among best actions
        best_actions = [a for a, q in q_values.items() if q == max_q]
        return random.choice(best_actions)
    
    def apply_action_constraints(self, action, current_connections):
        """
        Apply safety constraints to prevent invalid actions.
        Ensures fairness and avoids network congestion.
        """
        action_map = self.get_available_actions()
        change = action_map[action]
        new_connections = current_connections + change
        
        # Enforce bounds
        new_connections = max(self.min_connections, 
                             min(self.max_connections, new_connections))
        
        # Conservative behavior in poor conditions
        recent = list(self.metrics_history)[-3:] if len(self.metrics_history) >= 3 else []
        if recent:
            avg_loss = sum(m['packet_loss'] for m in recent) / len(recent)
            avg_rtt = sum(m['rtt'] for m in recent) / len(recent)
            
            # High loss or RTT: be conservative
            if (avg_loss > 5.0 or avg_rtt > 500) and change > 0:
                if LOG_RL_DECISIONS:
                    print("🔄 RL: Poor network conditions detected, limiting increase")
                change = min(1, change)  # Limit to +1 max
                new_connections = current_connections + change
        
        return max(self.min_connections, 
                  min(self.max_connections, new_connections))

    # ==================== Utility & Reward (Section 3.1.3) ====================
    
    def calculate_utility(self, throughput, packet_loss, num_streams):
        """
        Calculate utility function as per paper's Equation 3:
        U(n_i, T_i, L_i) = T_i / K^n_i - T_i × L_i × B
        
        Where:
        - T_i: throughput in Mbps
        - n_i: number of parallel streams
        - L_i: packet loss rate (as decimal, e.g., 0.01 for 1%)
        - K: cost-benefit parameter
        - B: punishment severity
        """
        # Convert packet loss percentage to decimal if needed
        loss_decimal = packet_loss / 100.0 if packet_loss > 1.0 else packet_loss
        
        # Performance term (diminishing returns with more streams)
        performance_term = throughput / (UTILITY_K ** num_streams)
        
        # Congestion punishment term
        congestion_term = throughput * loss_decimal * UTILITY_B
        
        utility = performance_term - congestion_term
        
        return utility
    
    def calculate_reward(self, prev_throughput, curr_throughput, 
                        prev_loss, curr_loss, num_streams):
        """
        Calculate reward based on utility change (Section 3.1.3).
        
        Paper's approach:
        - reward = x if U_t - U_{t-1} > ε (improvement)
        - reward = y if U_t - U_{t-1} < -ε (degradation)
        - reward = 0 otherwise (no significant change)
        """
        # Calculate utilities for both time steps
        prev_utility = self.calculate_utility(prev_throughput, prev_loss, num_streams)
        curr_utility = self.calculate_utility(curr_throughput, curr_loss, num_streams)
        
        utility_diff = curr_utility - prev_utility
        
        # Apply threshold-based reward (paper's approach)
        if utility_diff > UTILITY_EPSILON:
            reward = REWARD_POSITIVE
            self.performance_stats['total_positive_rewards'] += 1
        elif utility_diff < -UTILITY_EPSILON:
            reward = REWARD_NEGATIVE
            self.performance_stats['total_negative_rewards'] += 1
        else:
            reward = REWARD_NEUTRAL
        
        if LOG_RL_DECISIONS:
            print(f"   💰 Reward Calculation:")
            print(f"      Prev Utility: {prev_utility:.4f}, Curr Utility: {curr_utility:.4f}")
            print(f"      Utility Diff: {utility_diff:.4f}, Reward: {reward:.2f}")
        
        return reward

    # ==================== Q-Learning Update ====================
    
    def update_q_value(self, state, action, reward, next_state):
        """
        Q-learning update rule:
        Q(s,a) ← Q(s,a) + α[r + γ·max_a' Q(s',a') - Q(s,a)]
        
        This is the core learning mechanism.
        """
        current_q = self.get_q_value(state, action)
        
        # Get max Q-value for next state
        if next_state in self.Q:
            max_next_q = max(self.Q[next_state].values())
        else:
            max_next_q = 0.0
        
        # Q-learning update
        td_target = reward + self.discount_factor * max_next_q
        td_error = td_target - current_q
        new_q = current_q + self.learning_rate * td_error
        
        # Clip to prevent explosion
        new_q = max(-10, min(10, new_q))
        
        # Update Q-table
        if state not in self.Q:
            self.Q[state] = {a: 0.0 for a in range(5)}
        self.Q[state][action] = new_q
        
        self.total_learning_updates += 1
        
        if LOG_Q_TABLE_UPDATES:
            print(f"   📊 Q-Update: Q({state},{action}): {current_q:.3f} → {new_q:.3f}")
            print(f"      TD Error: {td_error:.4f}")

    # ==================== Decision Making (Main Interface) ====================
    
    def should_make_decision(self):
        """
        Check if enough time has passed since last decision.
        Implements the Monitoring Interval (MI) concept from the paper.
        """
        return time.time() - self.last_decision_time >= self.monitoring_interval
    
    def make_decision(self, throughput, rtt, packet_loss):
        """
        Main decision-making function called by the downloader.
        
        This implements the RL agent's action selection at each MI.
        Returns the optimal number of connections to use.
        """
        # Respect monitoring interval
        if not self.should_make_decision():
            return self.current_connections
        
        decision_start = time.time()
        self.total_decisions += 1
        
        try:
            # Create current state
            current_state = self.discretize_state(throughput, rtt, packet_loss)
            
            # Choose action
            action = self.choose_action(current_state)
            
            # Apply action to get new connection count
            new_connections = self.apply_action_constraints(action, self.current_connections)
            
            # Store for learning in next cycle
            self.last_state = current_state
            self.last_action = action
            self.last_metrics = {
                'throughput': throughput,
                'rtt': rtt,
                'packet_loss': packet_loss,
                'connections': self.current_connections
            }
            
            # Update connection count
            old_connections = self.current_connections
            self.current_connections = new_connections
            self.last_decision_time = time.time()
            
            # Logging
            if LOG_RL_DECISIONS:
                action_map = self.get_available_actions()
                print(f"\n🤖 RL Decision #{self.total_decisions}")
                print(f"   State: Throughput={throughput:.1f}Mbps, RTT={rtt:.1f}ms, Loss={packet_loss:.3f}%")
                print(f"   Discretized State: {current_state}")
                print(f"   Action: {action} ({action_map[action]:+d} streams)")
                print(f"   Connections: {old_connections} → {new_connections}")
                print(f"   Exploration Rate: {self.exploration_rate:.4f}")
                print(f"   Q-value: {self.get_q_value(current_state, action):.3f}")
            
            # Performance tracking
            if new_connections != old_connections:
                self.performance_stats['successful_adjustments'] += 1
            
            return self.current_connections
            
        except Exception as e:
            print(f"❌ RL Decision error: {e}")
            import traceback
            traceback.print_exc()
            return self.current_connections
    
    def learn_from_feedback(self, current_throughput, current_rtt, current_packet_loss):
        """
        Learn from the outcome of the previous action.
        
        This is called AFTER a monitoring interval to update the Q-table
        based on the observed results.
        
        Key fix: Uses STORED previous metrics vs CURRENT metrics for proper
        state transition: (S_t, A_t, R_t, S_{t+1})
        """
        # Need previous state and action to learn
        if self.last_state is None or self.last_action is None or self.last_metrics is None:
            # First iteration - just store metrics
            self.last_metrics = {
                'throughput': current_throughput,
                'rtt': current_rtt,
                'packet_loss': current_packet_loss,
                'connections': self.current_connections
            }
            return
        
        try:
            # Get previous metrics
            prev_throughput = self.last_metrics['throughput']
            prev_loss = self.last_metrics['packet_loss']
            
            # Calculate reward using previous and current metrics
            reward = self.calculate_reward(
                prev_throughput, current_throughput,
                prev_loss, current_packet_loss,
                self.current_connections
            )
            
            # Create next state from current metrics
            next_state = self.discretize_state(
                current_throughput, current_rtt, current_packet_loss
            )
            
            # Q-learning update: Q(S_t, A_t) based on R_t and S_{t+1}
            self.update_q_value(self.last_state, self.last_action, reward, next_state)
            
            # Store metrics for history and visualization
            self.metrics_history.append({
                'state': self.last_state,
                'action': self.last_action,
                'reward': reward,
                'throughput': current_throughput,
                'rtt': current_rtt,
                'packet_loss': current_packet_loss,
                'connections': self.current_connections,
                'timestamp': time.time()
            })
            
            # Update average reward
            recent_rewards = [m['reward'] for m in list(self.metrics_history)[-10:]]
            self.performance_stats['average_reward'] = sum(recent_rewards) / len(recent_rewards)
            
            # Auto-save Q-table periodically
            if self.total_learning_updates % Q_TABLE_SAVE_INTERVAL == 0:
                self.save_q_table()
            
            if LOG_RL_DECISIONS:
                print(f"   ✅ Learning completed (Update #{self.total_learning_updates})")
            
        except Exception as e:
            print(f"❌ RL Learning error: {e}")
            import traceback
            traceback.print_exc()

    # ==================== Persistence ====================
    
    def save_q_table(self):
        """Save Q-table to disk with backup."""
        try:
            # Convert tuple keys to strings for JSON serialization
            q_table_serializable = {}
            for state, actions in self.Q.items():
                state_str = str(state)
                q_table_serializable[state_str] = actions
            
            data = {
                'q_table': q_table_serializable,
                'metadata': {
                    'total_states': len(self.Q),
                    'total_decisions': self.total_decisions,
                    'total_updates': self.total_learning_updates,
                    'exploration_rate': self.exploration_rate,
                    'timestamp': time.time()
                }
            }
            
            # Atomic save with backup
            temp_file = Q_TABLE_FILE + '.tmp'
            with open(temp_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2)
            
            # Backup old file if exists
            if os.path.exists(Q_TABLE_FILE):
                os.replace(Q_TABLE_FILE, Q_TABLE_BACKUP)
            
            # Atomic rename
            os.replace(temp_file, Q_TABLE_FILE)
            
            if ENABLE_VERBOSE_LOGGING:
                print(f"💾 Q-table saved: {len(self.Q)} states, {self.total_learning_updates} updates")
            
        except Exception as e:
            print(f"❌ Error saving Q-table: {e}")
    
    def load_q_table(self):
        """Load Q-table from disk with validation."""
        try:
            if os.path.exists(Q_TABLE_FILE):
                with open(Q_TABLE_FILE, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                q_table_serializable = data.get('q_table', {})
                metadata = data.get('metadata', {})
                
                # Convert string keys back to tuples
                self.Q = {}
                for state_str, actions in q_table_serializable.items():
                    try:
                        state = eval(state_str)  # Safe here as we control the format
                        self.Q[state] = {int(k): v for k, v in actions.items()}
                    except:
                        continue
                
                # Restore metadata
                self.total_decisions = metadata.get('total_decisions', 0)
                self.total_learning_updates = metadata.get('total_updates', 0)
                saved_exploration = metadata.get('exploration_rate', self.exploration_rate)
                self.exploration_rate = max(saved_exploration, self.min_exploration_rate)
                
                print(f"✅ Q-table loaded: {len(self.Q)} states")
                print(f"   Previous decisions: {self.total_decisions}")
                print(f"   Learning updates: {self.total_learning_updates}")
                print(f"   Exploration rate: {self.exploration_rate:.4f}")
                
        except Exception as e:
            print(f"⚠️  Could not load Q-table: {e}")
            print("   Starting with empty Q-table")

    # ==================== Statistics & Monitoring ====================
    
    def get_stats(self):
        """Get comprehensive statistics for monitoring."""
        recent_rewards = [m['reward'] for m in list(self.metrics_history)[-10:]] if self.metrics_history else []
        avg_reward = sum(recent_rewards) / len(recent_rewards) if recent_rewards else 0
        
        return {
            'q_table_size': len(self.Q),
            'current_connections': self.current_connections,
            'exploration_rate': self.exploration_rate,
            'total_decisions': self.total_decisions,
            'total_learning_updates': self.total_learning_updates,
            'average_reward': avg_reward,
            'successful_adjustments': self.performance_stats['successful_adjustments'],
            'positive_rewards': self.performance_stats['total_positive_rewards'],
            'negative_rewards': self.performance_stats['total_negative_rewards'],
            'metrics_history_size': len(self.metrics_history),
            'monitoring_interval': self.monitoring_interval
        }
    
    def print_stats(self):
        """Print formatted statistics."""
        stats = self.get_stats()
        print("\n" + "="*60)
        print("📊 RL MANAGER STATISTICS")
        print("="*60)
        print(f"Q-table States:        {stats['q_table_size']}")
        print(f"Current Connections:   {stats['current_connections']}")
        print(f"Total Decisions:       {stats['total_decisions']}")
        print(f"Learning Updates:      {stats['total_learning_updates']}")
        print(f"Exploration Rate:      {stats['exploration_rate']:.4f}")
        print(f"Average Reward:        {stats['average_reward']:.4f}")
        print(f"Successful Adjusts:    {stats['successful_adjustments']}")
        print(f"Positive Rewards:      {stats['positive_rewards']}")
        print(f"Negative Rewards:      {stats['negative_rewards']}")
        print("="*60 + "\n")


# Global RL manager instance
rl_manager = RLConnectionManager()