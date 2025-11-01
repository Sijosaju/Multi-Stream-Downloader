"""
rl_manager.py - FIXED OPTIMIZED Reinforcement Learning Manager
Key fixes: Neutral Q-value initialization, no stability bonus, better exploration
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
    FIXED: Neutral initialization for better exploration
    """
    
    def __init__(self, 
                 learning_rate=RL_LEARNING_RATE, 
                 discount_factor=RL_DISCOUNT_FACTOR, 
                 exploration_rate=RL_EXPLORATION_RATE):
        # RL parameters
        self.learning_rate = learning_rate
        self.discount_factor = discount_factor
        self.exploration_rate = exploration_rate
        self.min_exploration_rate = RL_MIN_EXPLORATION
        self.exploration_decay = RL_EXPLORATION_DECAY
        
        # Q-table
        self.Q = {}
        
        # Connection management
        self.current_connections = DEFAULT_NUM_STREAMS
        self.max_connections = MAX_STREAMS
        self.min_connections = MIN_STREAMS
        
        # Monitoring interval tracking
        self.last_decision_time = time.time()
        self.monitoring_interval = RL_MONITORING_INTERVAL
        
        # State tracking
        self.last_state = None
        self.last_action = None
        self.last_metrics = None
        
        # Performance tracking
        self.metrics_history = deque(maxlen=50)
        self.total_decisions = 0
        self.total_learning_updates = 0
        
        # Action history for pattern detection
        self.action_history = deque(maxlen=10)
        
        # Performance improvement tracking
        self.performance_stats = {
            'successful_adjustments': 0,
            'total_positive_rewards': 0,
            'total_negative_rewards': 0,
            'average_reward': 0,
            'total_reward': 0,
            'throughput_improvements': 0,
            'stream_efficiency': 0,
            'optimal_range_usage': 0
        }
        
        # Load existing Q-table
        self.load_q_table()
        
        if ENABLE_VERBOSE_LOGGING:
            print("✅ RL Manager initialized (FIXED OPTIMIZED VERSION)")
            print(f"   Learning Rate: {self.learning_rate}")
            print(f"   Discount Factor: {self.discount_factor}")
            print(f"   Exploration Rate: {self.exploration_rate}")
            print(f"   Q-table size: {len(self.Q)} states")

    # ==================== State Representation ====================
    
    def discretize_state(self, throughput, rtt, packet_loss):
        """
        Optimized state discretization with balanced granularity.
        State = (throughput_level, rtt_level, loss_level)
        Total states: 6 × 4 × 5 = 120
        """
        # Throughput levels (Mbps)
        if throughput < 10:
            throughput_level = 0
        elif throughput < 20:
            throughput_level = 1
        elif throughput < 30:
            throughput_level = 2
        elif throughput < 40:
            throughput_level = 3
        elif throughput < 50:
            throughput_level = 4
        else:
            throughput_level = 5

        # RTT levels (ms)
        if rtt < 30:
            rtt_level = 0
        elif rtt < 80:
            rtt_level = 1
        elif rtt < 150:
            rtt_level = 2
        else:
            rtt_level = 3

        # Packet loss levels (%)
        if packet_loss < 0.1:
            loss_level = 0
        elif packet_loss < 0.5:
            loss_level = 1
        elif packet_loss < 1.0:
            loss_level = 2
        elif packet_loss < 2.0:
            loss_level = 3
        else:
            loss_level = 4

        return (throughput_level, rtt_level, loss_level)

    # ==================== Action Selection (FIXED) ====================
    
    def get_available_actions(self):
        """Available actions for stream adjustment."""
        return {
            0: 2,    # Aggressive Increase (+2)
            1: 1,    # Conservative Increase (+1)
            2: 0,    # No Change
            3: -1,   # Conservative Decrease (-1)
            4: -2    # Aggressive Decrease (-2)
        }
    
    def get_q_value(self, state, action):
        """
        FIXED: Get Q-value with NEUTRAL initialization.
        All actions start equal - only experience determines value.
        """
        if state not in self.Q:
            # FIXED: Neutral initialization (all actions equal)
            self.Q[state] = {a: 0.0 for a in range(5)}
        return self.Q[state].get(action, 0.0)
    
    def choose_action(self, state):
        """
        FIXED: ε-greedy with neutral initialization and enhanced exploration.
        """
        # Gradual exploration decay
        self.exploration_rate = max(
            self.min_exploration_rate,
            self.exploration_rate * self.exploration_decay
        )
        
        # FIXED: Initialize new states with neutral values
        if state not in self.Q:
            self.Q[state] = {a: 0.0 for a in range(5)}
        
        # Enhanced exploration for new/underexplored states
        state_visits = len([m for m in self.metrics_history if m['state'] == state])
        if state_visits < 3:  # New or rarely visited state
            effective_exploration = min(0.5, self.exploration_rate * 2.0)
        else:
            effective_exploration = self.exploration_rate
        
        # Exploration
        if random.random() < effective_exploration:
            # Weighted random to encourage trying different actions
            weights = [0.2, 0.2, 0.2, 0.2, 0.2]  # Equal weights
            action = random.choices(range(5), weights=weights)[0]
            self.action_history.append(action)
            return action
        
        # Exploitation
        q_values = self.Q[state]
        max_q = max(q_values.values())
        
        # Get all best actions
        best_actions = [a for a, q in q_values.items() if abs(q - max_q) < 0.001]
        
        # Oscillation prevention: avoid repeating increase/decrease patterns
        if len(self.action_history) >= 4:
            recent = list(self.action_history)[-4:]
            
            # Detect oscillation: [increase, decrease, increase, decrease]
            if (recent[0] in [0, 1] and recent[1] in [3, 4] and 
                recent[2] in [0, 1] and recent[3] in [3, 4]):
                # Prefer stability
                if 2 in best_actions:
                    action = 2
                else:
                    action = random.choice(best_actions)
            else:
                action = random.choice(best_actions)
        else:
            action = random.choice(best_actions)
        
        self.action_history.append(action)
        return action
    
    def apply_action_constraints(self, action, current_connections):
        """Apply action with intelligent constraints."""
        action_map = self.get_available_actions()
        change = action_map[action]
        new_connections = current_connections + change
        
        # Base bounds
        new_connections = max(self.min_connections, 
                             min(self.max_connections, new_connections))
        
        # Intelligent constraints based on network conditions
        recent = list(self.metrics_history)[-3:] if len(self.metrics_history) >= 3 else []
        
        if recent:
            avg_throughput = sum(m['throughput'] for m in recent) / len(recent)
            avg_loss = sum(m['packet_loss'] for m in recent) / len(recent)
            avg_rtt = sum(m['rtt'] for m in recent) / len(recent)
            
            # Excellent conditions - encourage optimal range (6-12)
            if avg_throughput > 30 and avg_loss < 0.5 and avg_rtt < 100:
                if new_connections < 6 and change < 0:
                    # Don't go below 6 in good conditions
                    if LOG_RL_DECISIONS:
                        print(f"🔄 RL: Good conditions, maintaining at least 6 streams")
                    return max(6, current_connections)
                elif new_connections > 12 and change > 0:
                    # Don't exceed 12 in good conditions
                    if LOG_RL_DECISIONS:
                        print(f"🔄 RL: Good conditions, capping at 12 streams")
                    return min(12, new_connections)
            
            # Poor conditions - be very conservative
            if avg_loss > 2.0 or avg_rtt > 200:
                if change > 0:
                    if LOG_RL_DECISIONS:
                        print("🔄 RL: Poor conditions, limiting increase")
                    return min(current_connections + 1, new_connections)
        
        return new_connections

    # ==================== OPTIMIZED Utility & Reward (FIXED) ====================
    
    def calculate_utility(self, throughput, packet_loss_pct, num_streams):
        """
        OPTIMIZED utility function with progressive stream costs.
        Strongly encourages optimal range of 6-12 streams.
        """
        # Convert to decimal
        loss_decimal = packet_loss_pct / 100.0
        loss_decimal = max(0.0001, min(0.1, loss_decimal))
        
        # Efficiency bonus
        if num_streams > 0:
            efficiency = throughput / num_streams
            efficiency_bonus = min(10.0, efficiency * 0.8) if efficiency > 4 else 0
        else:
            efficiency_bonus = 0
        
        # Base throughput with gentle diminishing returns
        throughput_value = throughput * (1.0 - throughput / (throughput + 100))
        
        # Loss penalty (quadratic)
        loss_penalty = throughput * (loss_decimal ** 2) * 30
        
        # PROGRESSIVE stream costs (key optimization)
        if num_streams <= 6:
            stream_cost = num_streams * 0.3
        elif num_streams <= 10:
            stream_cost = num_streams * 0.5  # Optimal range
        elif num_streams <= 14:
            stream_cost = num_streams * 1.0
        else:
            stream_cost = num_streams * 2.0  # Discourage high stream counts
        
        utility = throughput_value - loss_penalty - stream_cost + efficiency_bonus
        
        # SUBSTANTIAL bonus for optimal range (6-10 streams)
        if 6 <= num_streams <= 10:
            utility += 12.0  # Strong incentive
            self.performance_stats['optimal_range_usage'] += 1
        elif 4 <= num_streams <= 12:
            utility += 5.0  # Moderate incentive for extended range
        
        return utility
    
    def calculate_reward(self, prev_throughput, curr_throughput, 
                        prev_loss_pct, curr_loss_pct, num_streams):
        """
        FIXED: Reward calculation with proper sensitivity and NO stability bonus.
        """
        # Calculate utilities
        prev_utility = self.calculate_utility(prev_throughput, prev_loss_pct, num_streams)
        curr_utility = self.calculate_utility(curr_throughput, curr_loss_pct, num_streams)
        
        utility_diff = curr_utility - prev_utility
        
        # Adaptive threshold - more sensitive in optimal range
        base_threshold = UTILITY_EPSILON
        
        if 6 <= num_streams <= 12:
            threshold = base_threshold * 0.7
        else:
            threshold = base_threshold
        
        # Calculate reward with scaling
        if utility_diff > threshold:
            # Scale by magnitude of improvement
            reward_scale = min(3.0, 1.0 + abs(utility_diff) / 10.0)
            reward = REWARD_POSITIVE * reward_scale
            self.performance_stats['total_positive_rewards'] += 1
            if utility_diff > threshold * 2:
                self.performance_stats['throughput_improvements'] += 1
        elif utility_diff < -threshold:
            # Scale by magnitude of degradation
            reward_scale = min(3.0, 1.0 + abs(utility_diff) / 10.0)
            reward = REWARD_NEGATIVE * reward_scale
            self.performance_stats['total_negative_rewards'] += 1
        else:
            # FIXED: Pure neutral - no bonus for stability!
            reward = 0.0
        
        # Track total reward
        self.performance_stats['total_reward'] += reward
        
        if LOG_RL_DECISIONS:
            print(f"   💰 Reward Calculation (FIXED):")
            print(f"      Prev: T={prev_throughput:.1f}Mbps, L={prev_loss_pct:.3f}%, U={prev_utility:.2f}")
            print(f"      Curr: T={curr_throughput:.1f}Mbps, L={curr_loss_pct:.3f}%, U={curr_utility:.2f}")
            print(f"      Utility Diff: {utility_diff:.2f}, Reward: {reward:.2f}")
            if 6 <= num_streams <= 12:
                print(f"      🎯 IN OPTIMAL RANGE ({num_streams} streams)")
        
        return reward

    # ==================== Q-Learning Update ====================
    
    def update_q_value(self, state, action, reward, next_state):
        """Q-learning update with adaptive learning rate."""
        current_q = self.get_q_value(state, action)
        
        # Get max Q-value for next state
        if next_state in self.Q:
            max_next_q = max(self.Q[next_state].values())
        else:
            max_next_q = 0.0  # FIXED: Neutral for new states
        
        # Q-learning update
        td_target = reward + self.discount_factor * max_next_q
        td_error = td_target - current_q
        
        # Adaptive learning rate for significant updates
        if abs(reward) > 1.0:
            effective_lr = self.learning_rate * 1.5
        else:
            effective_lr = self.learning_rate
        
        new_q = current_q + effective_lr * td_error
        
        # Clip to reasonable range
        new_q = max(-10, min(10, new_q))
        
        # Update Q-table
        if state not in self.Q:
            self.Q[state] = {a: 0.0 for a in range(5)}
        self.Q[state][action] = new_q
        
        self.total_learning_updates += 1
        
        if LOG_Q_TABLE_UPDATES and abs(td_error) > 0.5:
            print(f"   📊 Q-Update: Q{(state,action)}: {current_q:.2f} → {new_q:.2f}")
            print(f"      TD Error: {td_error:.2f}, Reward: {reward:.2f}")

    # ==================== Decision Making ====================
    
    def should_make_decision(self):
        """Check if monitoring interval has passed."""
        return time.time() - self.last_decision_time >= self.monitoring_interval
    
    def make_decision(self, throughput, rtt, packet_loss_pct):
        """Main decision-making function."""
        if not self.should_make_decision():
            return self.current_connections
        
        decision_start = time.time()
        self.total_decisions += 1
        
        try:
            # Create state
            current_state = self.discretize_state(throughput, rtt, packet_loss_pct)
            
            # Choose action
            action = self.choose_action(current_state)
            
            # Apply action
            new_connections = self.apply_action_constraints(action, self.current_connections)
            
            # Store for learning
            self.last_state = current_state
            self.last_action = action
            self.last_metrics = {
                'throughput': throughput,
                'rtt': rtt,
                'packet_loss': packet_loss_pct,
                'connections': self.current_connections
            }
            
            # Update
            old_connections = self.current_connections
            self.current_connections = new_connections
            self.last_decision_time = time.time()
            
            # Logging
            if LOG_RL_DECISIONS:
                action_map = self.get_available_actions()
                action_names = {
                    0: "AGGR_INC", 1: "INC", 2: "STAY",
                    3: "DEC", 4: "AGGR_DEC"
                }
                print(f"\n🤖 RL Decision #{self.total_decisions}")
                print(f"   Metrics: T={throughput:.1f}Mbps, RTT={rtt:.1f}ms, Loss={packet_loss_pct:.2f}%")
                print(f"   State: {current_state}")
                print(f"   Action: {action} ({action_names[action]}: {action_map[action]:+d})")
                print(f"   Connections: {old_connections} → {new_connections}")
                print(f"   Exploration: {self.exploration_rate:.3f}")
                
                if 6 <= new_connections <= 12:
                    print(f"   🎯 OPTIMAL: {new_connections} streams")
                elif new_connections < 6:
                    print(f"   📉 BELOW: {new_connections} streams")
                else:
                    print(f"   📈 ABOVE: {new_connections} streams")
            
            if new_connections != old_connections:
                self.performance_stats['successful_adjustments'] += 1
            
            return self.current_connections
            
        except Exception as e:
            print(f"❌ RL Decision error: {e}")
            import traceback
            traceback.print_exc()
            return self.current_connections
    
    def learn_from_feedback(self, current_throughput, current_rtt, current_packet_loss_pct):
        """Learn from feedback."""
        if self.last_state is None or self.last_action is None or self.last_metrics is None:
            self.last_metrics = {
                'throughput': current_throughput,
                'rtt': current_rtt,
                'packet_loss': current_packet_loss_pct,
                'connections': self.current_connections
            }
            return
        
        try:
            # Get previous metrics
            prev_throughput = self.last_metrics['throughput']
            prev_loss = self.last_metrics['packet_loss']
            
            # Calculate reward
            reward = self.calculate_reward(
                prev_throughput, current_throughput,
                prev_loss, current_packet_loss_pct,
                self.current_connections
            )
            
            # Create next state
            next_state = self.discretize_state(
                current_throughput, current_rtt, current_packet_loss_pct
            )
            
            # Q-learning update
            self.update_q_value(self.last_state, self.last_action, reward, next_state)
            
            # Store metrics
            self.metrics_history.append({
                'state': self.last_state,
                'action': self.last_action,
                'reward': reward,
                'throughput': current_throughput,
                'rtt': current_rtt,
                'packet_loss': current_packet_loss_pct,
                'connections': self.current_connections,
                'timestamp': time.time()
            })
            
            # Update statistics
            if self.total_learning_updates > 0:
                self.performance_stats['average_reward'] = (
                    self.performance_stats['total_reward'] / self.total_learning_updates
                )
            
            if self.current_connections > 0:
                self.performance_stats['stream_efficiency'] = (
                    current_throughput / self.current_connections
                )
            
            # Auto-save
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
        """Save Q-table to disk."""
        try:
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
                    'average_reward': self.performance_stats['average_reward'],
                    'throughput_improvements': self.performance_stats['throughput_improvements'],
                    'optimal_range_usage': self.performance_stats['optimal_range_usage'],
                    'timestamp': time.time()
                }
            }
            
            temp_file = Q_TABLE_FILE + '.tmp'
            with open(temp_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2)
            
            if os.path.exists(Q_TABLE_FILE):
                os.replace(Q_TABLE_FILE, Q_TABLE_BACKUP)
            
            os.replace(temp_file, Q_TABLE_FILE)
            
            if ENABLE_VERBOSE_LOGGING:
                print(f"💾 Q-table saved: {len(self.Q)} states, avg reward: {self.performance_stats['average_reward']:.2f}")
            
        except Exception as e:
            print(f"❌ Error saving Q-table: {e}")
    
    def load_q_table(self):
        """Load Q-table from disk."""
        try:
            if os.path.exists(Q_TABLE_FILE):
                with open(Q_TABLE_FILE, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                q_table_serializable = data.get('q_table', {})
                metadata = data.get('metadata', {})
                
                self.Q = {}
                for state_str, actions in q_table_serializable.items():
                    try:
                        state = eval(state_str)
                        self.Q[state] = {int(k): v for k, v in actions.items()}
                    except:
                        continue
                
                self.total_decisions = metadata.get('total_decisions', 0)
                self.total_learning_updates = metadata.get('total_updates', 0)
                saved_exploration = metadata.get('exploration_rate', self.exploration_rate)
                self.exploration_rate = max(saved_exploration, self.min_exploration_rate)
                
                print(f"✅ Q-table loaded: {len(self.Q)} states")
                print(f"   Previous decisions: {self.total_decisions}")
                print(f"   Exploration rate: {self.exploration_rate:.3f}")
                
        except Exception as e:
            print(f"⚠️  Could not load Q-table: {e}")

    # ==================== Statistics ====================
    
    def get_stats(self):
        """Get comprehensive statistics."""
        total_updates = max(1, self.total_learning_updates)
        optimal_pct = (self.performance_stats['optimal_range_usage'] / total_updates * 100) if total_updates > 0 else 0
        
        return {
            'q_table_size': len(self.Q),
            'current_connections': self.current_connections,
            'exploration_rate': self.exploration_rate,
            'total_decisions': self.total_decisions,
            'total_learning_updates': self.total_learning_updates,
            'average_reward': self.performance_stats['average_reward'],
            'total_reward': self.performance_stats['total_reward'],
            'successful_adjustments': self.performance_stats['successful_adjustments'],
            'positive_rewards': self.performance_stats['total_positive_rewards'],
            'negative_rewards': self.performance_stats['total_negative_rewards'],
            'throughput_improvements': self.performance_stats['throughput_improvements'],
            'stream_efficiency': self.performance_stats['stream_efficiency'],
            'optimal_range_percentage': optimal_pct,
            'metrics_history_size': len(self.metrics_history),
            'monitoring_interval': self.monitoring_interval
        }
    
    def print_stats(self):
        """Print formatted statistics."""
        stats = self.get_stats()
        print("\n" + "="*70)
        print("📊 RL MANAGER STATISTICS (FIXED OPTIMIZED)")
        print("="*70)
        print(f"Q-table States:          {stats['q_table_size']}")
        print(f"Current Connections:     {stats['current_connections']}")
        print(f"Total Decisions:         {stats['total_decisions']}")
        print(f"Learning Updates:        {stats['total_learning_updates']}")
        print(f"Exploration Rate:        {stats['exploration_rate']:.3f}")
        print(f"Average Reward:          {stats['average_reward']:.3f}")
        print(f"Total Reward:            {stats['total_reward']:.1f}")
        print(f"Successful Adjustments:  {stats['successful_adjustments']}")
        print(f"Positive Rewards:        {stats['positive_rewards']}")
        print(f"Negative Rewards:        {stats['negative_rewards']}")
        print(f"Throughput Improvements: {stats['throughput_improvements']}")
        print(f"Stream Efficiency:       {stats['stream_efficiency']:.1f} Mbps/stream")
        print(f"Optimal Range Usage:     {stats['optimal_range_percentage']:.1f}%")
        
        # Range assessment
        connections = stats['current_connections']
        if 6 <= connections <= 12:
            range_status = "🎯 OPTIMAL"
        elif connections < 6:
            range_status = "📉 BELOW OPTIMAL"
        else:
            range_status = "📈 ABOVE OPTIMAL"
        print(f"Current Range:           {range_status}")
        
        # Success rate
        total_rewards = stats['positive_rewards'] + stats['negative_rewards']
        if total_rewards > 0:
            success_rate = stats['positive_rewards'] / total_rewards * 100
            print(f"Success Rate:            {success_rate:.1f}%")
        
        print("="*70 + "\n")


# Global RL manager instance
rl_manager = RLConnectionManager()