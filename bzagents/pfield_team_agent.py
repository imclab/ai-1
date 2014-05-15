#!/usr/bin/python -tt
#################################################################
# python pfield_team_agent.py [hostname] [port]
#################################################################

import sys
import math
import time
from threading import Thread
from bzrc import BZRC, Command
from potential_fields import *
from utilities import ThreadSafeQueue
from graph import PotentialFieldGraph
from env import EnvironmentState


class TeamManager(object):
    """Handle all command and control logic for a team of tanks."""
    def __init__(self, bzrc):
        self.bzrc = bzrc
        self.env_constants = self.bzrc.get_environment_constants()
        self.tanks = []
        for i in range(0, 10):
            self.tanks.append(PFieldTank(i, self.bzrc, self.env_constants))
        for tank in self.tanks:
            tank.setDaemon(True)
            tank.start()
    
    def play(self):
        """Start playing BZFlag!"""
        prev_time = time.time()

        # Continuously get the environment state and have each tank update
        try:
            while True:
                time_diff = time.time() - prev_time
                self.tick(time_diff)
        except KeyboardInterrupt:
            print "Exiting due to keyboard interrupt."
            bzrc.close()
    
    def tick(self, time_diff):
        """Get a new state."""
        env_state = self.bzrc.get_environment_state(self.env_constants.color, )
        env_state.time_diff = time_diff
        for tank in self.tanks:
            tank.add_env_state(env_state)    

class PFieldTank(Thread):
    """Handle all command and control logic for a single tank."""
    
    def __init__(self, index, bzrc, env_constants):
        """The brain must take in a state and produce a command."""
        super(PFieldTank, self).__init__()
        self.index = index
        self.bzrc = bzrc
        self.error = 0
        self.env_states = ThreadSafeQueue()
        self.env_constants = env_constants
        self.keep_running = True
        self.graph = None
    
    def start_plotting(self):
        if not self.graph:
            self.graph = PotentialFieldGraph(self.env_constants.get_worldsize())
            self.graph.setDaemon(True)
            self.graph.start()
    
    def stop_plotting(self):
        if self.graph:
            self.graph.stop()
            
    def stop(self):
        self.keep_running = False
    
    def add_env_state(self, env_state):
        self.env_states.add(env_state)
    
    def remove_env_state(self):
        result = self.env_states.remove()
        while len(self.env_states) > 0:
            result = self.env_states.remove()
        return result
    
    def run(self):
        while self.keep_running:
            s = self.remove_env_state()
            self.behave(s)

    def closest_flag(self, flags, tank, flags_captured):
        closest_dist = sys.maxint
        chosen_flag = flags[0]
        for flag in flags:
            distance = compute_distance(flag.x, tank.x, flag.y, tank.y)
            if distance < closest_dist and not flags_captured.__contains__(flag.color):
                closest_dist = distance
                chosen_flag = flag 
        return chosen_flag

    def behave(self, env_state):
        """Create a behavior command based on potential fields given an environment state."""
        env_constants = self.env_constants
        tank = env_state.get_mytank(self.index)
        
        bag_o_fields = []
        # avoid enemies
        for enemy in env_state.enemytanks:
            if enemy.status == self.env_constants.alive:
                bag_o_fields.append(make_circle_repulsion_function(enemy.x, enemy.y, env_constants.tanklength, env_constants.tanklength*5, 2))

        
        # avoid shots
        for shot in env_state.shots:
            bag_o_fields.append(make_circle_repulsion_function(shot.x, shot.y, env_constants.tanklength, env_constants.tanklength*3, 2))

        enemy_flags = env_state.enemyflags
        our_flag = env_state.myflag

        #if another tank on your team has a flag, that tank becomes a tangential field
        #also, make sure that any flag that a teammate is carrying is no longer attractive
        flags_captured = []
        for my_tank in env_state.mytanks:
            if my_tank != tank and my_tank.flag != "-":
                bag_o_fields.append(make_tangential_function(my_tank.x, my_tank.y, env_constants.tanklength, 80, 1, 20))
                flags_captured.append(my_tank.flag)

        #if an enemy tank has captured our flag, they become a priority
        public_enemy = None
        for other_tank in env_state.enemytanks:
            if other_tank.flag == env_constants.color:
                public_enemy = other_tank

        if tank.flag != "-":
            goal = self.base 
            cr = (self.base.corner1_x - self.base.corner2_x) / 2
            goal.x = self.base.corner1_x + cr
            goal.y = self.base.corner1_y + cr
            cs = 10
            a = 3
        elif public_enemy is not None:
            goal1 = public_enemy
            goal2 = self.closest_flag(enemy_flags, tank, flags_captured)
            dist_goal1 = compute_distance(goal1.x, tank.x, goal1.y, tank.y)
            dist_goal2 = compute_distance(goal2.x, tank.x, goal2.y, tank.y)
            if dist_goal1 < dist_goal2:
                goal = goal1 
                cr = int(env_constants.tanklength)
                cs = 20
                a = 3
            else:
                goal = goal2
                cr = 2
                cs = 20
                a = 2
        else:
            goal = self.closest_flag(enemy_flags, tank, flags_captured)
            cr = 2
            cs = 20
            a = 2
        bag_o_fields.append(make_circle_attraction_function(goal.x, goal.y, cr, cs, a))

        
        def pfield_function(x, y):
            dx = 0
            dy = 0
            for field_function in bag_o_fields:
                newdx, newdy = field_function(x, y)
                dx += newdx
                dy += newdy
            return dx, dy
        
        dx, dy = pfield_function(tank.x, tank.y)
        self.move_to_position(tank, tank.x + dx, tank.y + dy)
    
    def attack_enemies(self, tank):
        """Find the closest enemy and chase it, shooting as you go."""
        best_enemy = None
        best_dist = 2 * float(self.constants['worldsize'])
        for enemy in self.enemies:
            if enemy.status != 'alive':
                continue
            dist = math.sqrt((enemy.x - tank.x)**2 + (enemy.y - tank.y)**2)
            if dist < best_dist:
                best_dist = dist
                best_enemy = enemy
        if best_enemy is None:
            command = Command(tank.index, 0, 0, False)
            self.commands.append(command)
        else:
            self.move_to_position(tank, best_enemy.x, best_enemy.y)

    def move_to_position(self, tank, target_x, target_y):
        """Set command to move to given coordinates."""
        target_angle = math.atan2(target_y - tank.y,
                                  target_x - tank.x)
        relative_angle = self.normalize_angle(target_angle - tank.angle)
        command = Command(tank.index, 1, 2 * relative_angle, True)
        self.bzrc.do_commands([command])

    def normalize_angle(self, angle):
        """Make any angle be between +/- pi."""
        angle -= 2 * math.pi * int (angle / (2 * math.pi))
        if angle <= -math.pi:
            angle += 2 * math.pi
        elif angle > math.pi:
            angle -= 2 * math.pi
        return angle

def main():
    # Process CLI arguments.
    try:
        execname, host, port = sys.argv
    except ValueError:
        execname = sys.argv[0]
        print >>sys.stderr, '%s: incorrect number of arguments' % execname
        print >>sys.stderr, 'usage: %s hostname port' % sys.argv[0]
        sys.exit(-1)

    # Connect.
    #bzrc = BZRC(host, int(port), debug=True)
    bzrc = BZRC(host, int(port))

    team = TeamManager(bzrc)
    team.play()

if __name__ == '__main__':
    main()

# vim: et sw=4 sts=4
