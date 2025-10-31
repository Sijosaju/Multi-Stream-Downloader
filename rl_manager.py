"""
rl_manager.py - OPTIMIZED Reinforcement Learning Manager
Final version with balanced stream optimization
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
    OPTIMIZED: Balanced utility function with progressive stream costs
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
        
        # Action history for oscillation prevention
        self.action_history = deque(maxlen=5)
        
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
            print("✅ RL Manager initialized (OPTIMIZED VERSION)")
            print(f"   Learning Rate: {self.learning_rate}")
            print(f"   Discount Factor: {self.discount_factor}")
            print(f"   Exploration Rate: {self.exploration_rate}")
            print(f"   Q-table size: {len(self.Q)} states")

    # ==================== State Representation ====================
    
    def discretize_state(self, throughput, rtt, packet_loss):
        """
        Optimized state discretization with balanced levels.
        State = (throughput_level, rtt_level, loss_level)
        """
        # Throughput levels (Mbps) - balanced granularity
        if throughput < 10:
            throughput_level = 0  # Very Low
        elif throughput < 20:
            throughput_level = 1  # Low
        elif throughput < 30:
            throughput_level = 2  # Medium-Low
        elif throughput < 40:
            throughput_level = 3  # Medium
        elif throughput < 50:
            throughput_level = 4  # Medium-High
        else:
            throughput_level = 5  # High

        # RTT levels (ms)
        if rtt < 30:
            rtt_level = 0  # Excellent
        elif rtt < 80:
            rtt_level = 1  # Good
        elif rtt < 150:
            rtt_level = 2  # Fair
        else:
            rtt_level = 3  # Poor

        # Packet loss levels (%)
        if packet_loss < 0.1:
            loss_level = 0  # Excellent
        elif packet_loss < 0.5:
            loss_level = 1  # Good
        elif packet_loss < 1.0:
            loss_level = 2  # Fair
        elif packet_loss < 2.0:
            loss_level = 3  # Poor
        else:
            loss_level = 4  # Very Poor

        return (throughput_level, rtt_level, loss_level)

    # ==================== Action Selection ====================
    
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
        """Get Q-value with balanced initialization."""
        if state not in self.Q:
            # Initialize with balanced values favoring optimal range
            initial_values = {
                0: 1.2,  # Aggressive Increase
                1: 1.5,  # Conservative Increase
                2: 1.8,  # No Change - most optimistic
                3: 1.3,  # Conservative Decrease
                4: 0.8   # Aggressive Decrease
            }
            self.Q[state] = initial_values
        return self.Q[state].get(action, 1.0)
    
    def choose_action(self, state):
        """ε-greedy with balanced exploration and exploitation."""
        # Gradual exploration decay
        self.exploration_rate = max(
            self.min_exploration_rate,
            self.exploration_rate * self.exploration_decay
        )
        
        # Initialize state if new
        if state not in self.Q:
            initial_values = {
                0: 1.2,  # Aggressive Increase
                1: 1.5,  # Conservative Increase
                2: 1.8,  # No Change
                3: 1.3,  # Conservative Decrease
                4: 0.8   # Aggressive Decrease
            }
            self.Q[state] = initial_values
    
        # Exploration with probability epsilon
        if random.random() < self.exploration_rate:
            # Balanced random exploration
            weights = [0.15, 0.20, 0.35, 0.20, 0.10]  # Favor stability
            action = random.choices(range(5), weights=weights)[0]
            self.action_history.append(action)
            return action
        
        # Exploitation with tie-breaking
        q_values = self.Q[state]
        max_q = max(q_values.values())
        best_actions = [a for a, q in q_values.items() if q == max_q]
        
        # Context-aware action selection
        if len(self.action_history) >= 3:
            recent_actions = list(self.action_history)
            
            # If we've been increasing too much, prefer stability or decrease
            if sum(1 for a in recent_actions if a in [0, 1]) >= 2:
                if 2 in best_actions:  # Prefer no change
                    action = 2
                elif any(a in [3, 4] for a in best_actions):  # Prefer decrease
                    decrease_actions = [a for a in best_actions if a in [3, 4]]
                    action = random.choice(decrease_actions) if decrease_actions else random.choice(best_actions)
                else:
                    action = random.choice(best_actions)
            # If we've been decreasing too much, prefer stability or increase
            elif sum(1 for a in recent_actions if a in [3, 4]) >= 2:
                if 2 in best_actions:  # Prefer no change
                    action = 2
                elif any(a in [0, 1] for a in best_actions):  # Prefer increase
                    increase_actions = [a for a in best_actions if a in [0, 1]]
                    action = random.choice(increase_actions) if increase_actions else random.choice(best_actions)
                else:
                    action = random.choice(best_actions)
            else:
                action = random.choice(best_actions)
        else:
            action = random.choice(best_actions)
        
        self.action_history.append(action)
        return action
    
    def apply_action_constraints(self, action, current_connections):
        """Apply action with intelligent constraints for optimal range."""
        action_map = self.get_available_actions()
        change = action_map[action]
        new_connections = current_connections + change
        
        # Base bounds
        new_connections = max(self.min_connections, 
                             min(self.max_connections, new_connections))
        
        # Intelligent constraints based on network conditions and optimal range
        recent_metrics = list(self.metrics_history)[-3:] if len(self.metrics_history) >= 3 else []
        
        if recent_metrics:
            avg_throughput = sum(m['throughput'] for m in recent_metrics) / len(recent_metrics)
            avg_loss = sum(m['packet_loss'] for m in recent_metrics) / len(recent_metrics)
            avg_rtt = sum(m['rtt'] for m in recent_metrics) / len(recent_metrics)
            
            # Optimal conditions - encourage exploration in 6-12 range
            if avg_throughput > 30 and avg_loss < 0.5 and avg_rtt < 100:
                optimal_min, optimal_max = 6, 12
                
                if new_connections < optimal_min and change < 0:
                    # Don't decrease below optimal minimum in good conditions
                    if LOG_RL_DECISIONS:
                        print(f"🔄 RL: Good conditions, maintaining at least {optimal_min} streams")
                    return max(optimal_min, current_connections)
                elif new_connections > optimal_max and change > 0:
                    # Be cautious about exceeding optimal maximum
                    if LOG_RL_DECISIONS:
                        print(f"🔄 RL: Approaching optimal max, limiting increase")
                    return min(optimal_max, new_connections)
            
            # Poor conditions - be conservative
            if avg_loss > 2.0 or avg_rtt > 200:
                if change > 0:
                    # Limit increases in poor conditions
                    if LOG_RL_DECISIONS:
                        print("🔄 RL: Poor conditions, limiting increase")
                    return min(current_connections + 1, new_connections)
                elif change < -1:
                    # Allow decreases but not too aggressive
                    return max(current_connections - 1, new_connections)
        
        return new_connections

    # ==================== OPTIMIZED Utility & Reward ====================
    
    def calculate_utility(self, throughput, packet_loss_pct, num_streams):
        """
        OPTIMIZED utility function with progressive stream costs.
        Encourages optimal range of 6-12 streams.
        """
        # Convert packet loss percentage to decimal
        loss_decimal = packet_loss_pct / 100.0
        
        # Efficiency factor - reward efficient use of streams
        if num_streams > 0:
            efficiency = throughput / num_streams
            # High efficiency with multiple streams gets substantial bonus
            efficiency_bonus = min(10.0, efficiency * 1.0) if efficiency > 4 else 0
        else:
            efficiency_bonus = 0
        
        # Base throughput value with gentle diminishing returns
        throughput_value = throughput * (1.0 - throughput / (throughput + 80))
        
        # Loss penalty (increases exponentially with loss)
        loss_penalty = throughput * (loss_decimal ** 2) * 20
        
        # PROGRESSIVE STREAM COST - key optimization
        if num_streams <= 6:
            stream_cost = num_streams * 0.2  # Very low cost for minimal streams
        elif num_streams <= 10:
            stream_cost = num_streams * 0.4  # Low cost for optimal range
        elif num_streams <= 14:
            stream_cost = num_streams * 0.8  # Medium cost for extended range
        else:
            stream_cost = num_streams * 1.5  # High cost for excessive streams
        
        utility = throughput_value - loss_penalty - stream_cost + efficiency_bonus
        
        # SUBSTANTIAL bonus for optimal stream range (6-10 streams)
        if 6 <= num_streams <= 10:
            utility += 8.0
            self.performance_stats['optimal_range_usage'] += 1
        elif 4 <= num_streams <= 12:
            utility += 3.0  # Smaller bonus for extended optimal range
        
        return utility
    
    def calculate_reward(self, prev_throughput, curr_throughput, 
                        prev_loss_pct, curr_loss_pct, num_streams):
        """
        Optimized reward calculation with adaptive sensitivity.
        """
        # Calculate utilities
        prev_utility = self.calculate_utility(prev_throughput, prev_loss_pct, num_streams)
        curr_utility = self.calculate_utility(curr_throughput, curr_loss_pct, num_streams)
        
        utility_diff = curr_utility - prev_utility
        
        # Adaptive threshold based on throughput level and stream count
        base_threshold = UTILITY_EPSILON
        
        # More sensitive to changes when in optimal range
        if 6 <= num_streams <= 12:
            threshold = base_threshold * 0.7
        else:
            threshold = base_threshold
        
        # Calculate reward with enhanced sensitivity
        if utility_diff > threshold:
            # Scale positive reward by improvement magnitude
            reward_scale = min(3.0, (utility_diff / max(1.0, abs(prev_utility))) * 2)
            reward = REWARD_POSITIVE * reward_scale
            self.performance_stats['total_positive_rewards'] += 1
            if utility_diff > threshold * 2:
                self.performance_stats['throughput_improvements'] += 1
        elif utility_diff < -threshold:
            # Scale negative reward by degradation magnitude
            reward_scale = min(3.0, (abs(utility_diff) / max(1.0, abs(prev_utility))) * 2)
            reward = REWARD_NEGATIVE * reward_scale
            self.performance_stats['total_negative_rewards'] += 1
        else:
            # Small positive reward for stability in optimal range
            if 6 <= num_streams <= 12:
                reward = REWARD_NEUTRAL * 0.8
            else:
                reward = REWARD_NEUTRAL * 0.3
        
        # Track total reward
        self.performance_stats['total_reward'] += reward
        
        if LOG_RL_DECISIONS:
            print(f"   💰 Reward Calculation (OPTIMIZED):")
            print(f"      Prev: T={prev_throughput:.1f}Mbps, L={prev_loss_pct:.3f}%, U={prev_utility:.4f}")
            print(f"      Curr: T={curr_throughput:.1f}Mbps, L={curr_loss_pct:.3f}%, U={curr_utility:.4f}")
            print(f"      Utility Diff: {utility_diff:.4f}, Reward: {reward:.2f}")
            if 6 <= num_streams <= 12:
                print(f"      🎯 IN OPTIMAL RANGE (6-12 streams)")
        
        return reward

    # ==================== Q-Learning Update ====================
    
    def update_q_value(self, state, action, reward, next_state):
        """Q-learning update with enhanced learning for optimal range."""
        current_q = self.get_q_value(state, action)
        
        # Get max Q-value for next state
        if next_state in self.Q:
            max_next_q = max(self.Q[next_state].values())
        else:
            max_next_q = 1.0  # Optimistic initial value
        
        # Q-learning update with momentum
        td_target = reward + self.discount_factor * max_next_q
        td_error = td_target - current_q
        
        # Enhanced learning rate for significant rewards
        if abs(reward) > REWARD_POSITIVE * 0.5:
            effective_lr = self.learning_rate * 2.0
        else:
            effective_lr = self.learning_rate
        
        new_q = current_q + effective_lr * td_error
        
        # Clip to reasonable range
        new_q = max(-10, min(10, new_q))
        
        # Update Q-table
        if state not in self.Q:
            self.Q[state] = {a: 1.0 for a in range(5)}
        self.Q[state][action] = new_q
        
        self.total_learning_updates += 1
        
        if LOG_Q_TABLE_UPDATES and abs(td_error) > 0.1:
            print(f"   📊 Q-Update: Q{(state,action)}: {current_q:.3f} → {new_q:.3f}")
            print(f"      TD Error: {td_error:.4f}, Reward: {reward:.2f}")

    # ==================== Decision Making ====================
    
    def should_make_decision(self):
        """Check if monitoring interval has passed."""
        return time.time() - self.last_decision_time >= self.monitoring_interval
    
    def make_decision(self, throughput, rtt, packet_loss_pct):
        """
        Main decision-making function.
        """
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
                    0: "AGGR_INCREASE", 1: "CONS_INCREASE", 2: "NO_CHANGE",
                    3: "CONS_DECREASE", 4: "AGGR_DECREASE"
                }
                print(f"\n🤖 RL Decision #{self.total_decisions}")
                print(f"   Metrics: T={throughput:.1f}Mbps, RTT={rtt:.1f}ms, Loss={packet_loss_pct:.3f}%")
                print(f"   State: {current_state}")
                print(f"   Action: {action} ({action_names[action]}: {action_map[action]:+d})")
                print(f"   Connections: {old_connections} → {new_connections}")
                print(f"   Exploration: {self.exploration_rate:.4f}")
                
                # Highlight optimal range
                if 6 <= new_connections <= 12:
                    print(f"   🎯 OPTIMAL RANGE: {new_connections} streams")
                elif new_connections < 6:
                    print(f"   📉 BELOW OPTIMAL: {new_connections} streams")
                else:
                    print(f"   📈 ABOVE OPTIMAL: {new_connections} streams")
            
            if new_connections != old_connections:
                self.performance_stats['successful_adjustments'] += 1
            
            return self.current_connections
            
        except Exception as e:
            print(f"❌ RL Decision error: {e}")
            import traceback
            traceback.print_exc()
            return self.current_connections
    
    def learn_from_feedback(self, current_throughput, current_rtt, current_packet_loss_pct):
        """
        Learn from feedback with enhanced tracking.
        """
        if self.last_state is None or self.last_action is None or self.last_metrics is None:
            # First iteration
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
            
            # Update performance statistics
            if self.total_learning_updates > 0:
                self.performance_stats['average_reward'] = (
                    self.performance_stats['total_reward'] / self.total_learning_updates
                )
            
            # Calculate stream efficiency
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
                print(f"💾 Q-table saved: {len(self.Q)} states, avg reward: {self.performance_stats['average_reward']:.3f}")
            
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
                print(f"   Exploration rate: {self.exploration_rate:.4f}")
                
        except Exception as e:
            print(f"⚠️  Could not load Q-table: {e}")

    # ==================== Statistics ====================
    
    def get_stats(self):
        """Get comprehensive statistics."""
        total_updates = max(1, self.total_learning_updates)
        optimal_percentage = (self.performance_stats['optimal_range_usage'] / total_updates * 100) if total_updates > 0 else 0
        
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
            'optimal_range_percentage': optimal_percentage,
            'metrics_history_size': len(self.metrics_history),
            'monitoring_interval': self.monitoring_interval
        }
    
    def print_stats(self):
        """Print formatted statistics."""
        stats = self.get_stats()
        print("\n" + "="*60)
        print("📊 RL MANAGER STATISTICS (OPTIMIZED)")
        print("="*60)
        print(f"Q-table States:        {stats['q_table_size']}")
        print(f"Current Connections:   {stats['current_connections']}")
        print(f"Total Decisions:       {stats['total_decisions']}")
        print(f"Learning Updates:      {stats['total_learning_updates']}")
        print(f"Exploration Rate:      {stats['exploration_rate']:.4f}")
        print(f"Average Reward:        {stats['average_reward']:.4f}")
        print(f"Total Reward:          {stats['total_reward']:.1f}")
        print(f"Successful Adjusts:    {stats['successful_adjustments']}")
        print(f"Positive Rewards:      {stats['positive_rewards']}")
        print(f"Negative Rewards:      {stats['negative_rewards']}")
        print(f"Throughput Improvements: {stats['throughput_improvements']}")
        print(f"Stream Efficiency:     {stats['stream_efficiency']:.1f} Mbps/stream")
        print(f"Optimal Range Usage:   {stats['optimal_range_percentage']:.1f}%")
        
        # Range assessment
        connections = stats['current_connections']
        if 6 <= connections <= 12:
            range_status = "🎯 OPTIMAL"
        elif connections < 6:
            range_status = "📉 BELOW OPTIMAL"
        else:
            range_status = "📈 ABOVE OPTIMAL"
        print(f"Current Range:         {range_status}")
        
        # Compute success rate
        total_rewards = stats['positive_rewards'] + stats['negative_rewards']
        if total_rewards > 0:
            success_rate = stats['positive_rewards'] / total_rewards * 100
            print(f"Success Rate:          {success_rate:.1f}%")
        
        print("="*60 + "\n")


# Global RL manager instance
rl_manager = RLConnectionManager()