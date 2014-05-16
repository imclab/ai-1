#!/usr/bin/env python

import OpenGL
OpenGL.ERROR_CHECKING = False
from OpenGL.GL import *
from OpenGL.GLUT import *
from OpenGL.GLU import *
import numpy
from numpy import zeros
from threading import Thread, Lock
import time


class ObstacleVisualization(Thread):
    def __init__(self, width, height):
        super(ObstacleVisualization, self).__init__()
        self.grid = None
        self.width = width
        self.height = height
        self.lock = Lock()
    
    def run(self):
        self.init_window(self.width, self.height)
    
    def draw_grid(self):
        # This assumes you are using a numpy array for your grid
        width, height = self.grid.shape
        glRasterPos2f(-1, -1)
        glDrawPixels(width, height, GL_LUMINANCE, GL_FLOAT, self.grid)
        glFlush()
        glutSwapBuffers()

    def update_grid(self, new_grid):
        self.lock.acquire()
        self.grid = new_grid
        #~ glutPostRedisplay()
        self.lock.release()
    
    # mostly used for testing
    def update_grid_values(self, num):
        self.lock.acquire()
        self.grid[:] = num
        #~ glutPostRedisplay()
        self.lock.release()

    def init_window(self, width, height):
        self.grid = zeros((width, height))
        #~ self.grid = numpy.empty((width, height))
        #~ self.grid[:] = 0.25
        self.lock.acquire()
        glutInit(sys.argv)
        glutInitDisplayMode(GLUT_RGBA | GLUT_DOUBLE | GLUT_ALPHA | GLUT_DEPTH)
        glutInitWindowSize(width, height)
        glutInitWindowPosition(0, 0)
        self.window = glutCreateWindow("Grid Filter")
        glutDisplayFunc(self.draw_grid)
        glMatrixMode(GL_PROJECTION)
        glLoadIdentity()
        glMatrixMode(GL_MODELVIEW)
        glLoadIdentity()
        #~ time.sleep(2)
        self.lock.release()
        glutMainLoop()

class Grid(object):
    INITIAL_OBSTACLE_PROBABILITY = 0.7
    DEFAULT_TRUE_POSITIVE = 0.97
    DEFAULT_TRUE_NEGATIVE = 0.9
    OBSTACLE = 1
    NOT_OBSTACLE = 0
    
    def __init__(self, width, height):
        self.vis = ObstacleVisualization(width, height)
        self.vis.start()
        self.grid = numpy.empty((width, height))
        self.grid[:] = Grid.INITIAL_OBSTACLE_PROBABILITY
        self.set_true_positive(Grid.DEFAULT_TRUE_POSITIVE)
        self.set_true_negative(Grid.DEFAULT_TRUE_NEGATIVE)
        self.update_thresholds()
        
    def update_thresholds(self):
        self.obstacle_threshold = self.cond_prob_obstacle_obstacle # any probability above this is considered an obstacle
        self.not_obstacle_threshold = self.cond_prob_obstacle_not_obstacle # any probability below this is considered to not be an obstacle
        if self.obstacle_threshold < self.not_obstacle_threshold:
            temp = self.not_obstacle_threshold
            self.not_obstacle_threshold = self.obstacle_threshold
            self.obstacle_threshold = temp
        
    def set_true_positive(self, prob):
        self.prob_true_positive = prob
        # P(o_i,j=obstacle|s_i,j=obstacle)
        self.cond_prob_obstacle_obstacle = self.prob_true_positive
        # P(o_i,j=not_obstacle|s_i,j=obstacle)
        self.cond_prob_not_obstacle_obstacle = 1 - self.cond_prob_obstacle_obstacle
    
    def set_true_negative(self, prob):
        self.prob_true_negative = prob
        # P(o_i,j=not_obstacle|s_i,j=not_obstacle)
        self.cond_prob_not_obstacle_not_obstacle = self.prob_true_negative
        # P(o_i,j=obstacle|s_i,j=not_obstacle)
        self.cond_prob_obstacle_not_obstacle = 1 - self.cond_prob_not_obstacle_not_obstacle
    
    def update_cell(self, i, j, observation):
        self.grid[i, j] = self.calculate_conditional_probability(self.grid[i, j], observation)

    #returns P(s_i,j = occupied | o_i,j) the main conditional probability that we want
    def calculate_conditional_probability(self, prob_state_is_obstacle, observation):
        """Return the new probability that a cell contains an obstacle."""
        # P(s_i,j=obstacle | o_i,j=obstacle)
        if observation == Grid.OBSTACLE:
            cp_obs_obs_1 = self.cond_prob_obstacle_obstacle*prob_state_is_obstacle
            cp_obs_obs_2 = self.cond_prob_obstacle_not_obstacle*(1 - prob_state_is_obstacle)
            return cp_obs_obs_1/(cp_obs_obs_1 + cp_obs_obs_2)
        elif observation == Grid.NOT_OBSTACLE:
            cp_obs_not_obs_1 = self.cond_prob_not_obstacle_obstacle*(prob_state_is_obstacle)
            cp_obs_not_obs_2 = self.cond_prob_not_obstacle_not_obstacle*(1-prob_state_is_obstacle)
            return cp_obs_not_obs_1/(cp_obs_not_obs_1 + cp_obs_not_obs_2)
        else:
            return prob_state_is_obstacle # no observation, return previous state
    
    def get_item(self, x, y):
        return self.grid[x, y]
    
    #to be called in the tick method.
    def update(self, corner_x, corner_y, mini_grid):
        """mini_grid is a numpy matrix of ones and zeros
        The corner is the starting corner in the map when rotated correctly.
        """
        (i_len, j_len) = mini_grid.shape
        
        for i in xrange(0, i_len):
            for j in xrange(0, j_len):
                self.update_cell(i + corner_x, j + corner_y, mini_grid[i, j])
        
        self.vis.update_grid(self.grid)

if __name__ == "__main__":
    #~ ov = ObstacleVisualization(800, 800)
    #~ ov.start()
    #~ num = 0
    #~ inc = 0.03
    #~ while ov.is_alive():
        #~ num += inc
        #~ ov.update_grid_values(num)
        #~ time.sleep(2)
        #~ if num >= 1:
            #~ inc *= -1
    #~ ov.join()
    g = Grid(800, 800)
    while True:
        time.sleep(2)
        mini_grid = numpy.empty((50, 50))
        mini_grid[:] = 1
        g.update(0, 0, mini_grid)

# vim: et sw=4 sts=4
