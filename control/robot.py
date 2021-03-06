from distance import distance
from pathSmooth import pathSmooth
import PID
from enum import Enum
import wrapper
from numpy import clip, binary_repr
import math


ROTATION_SCALE = 190
ROTATION_MID = 465
MAX_CLOSE_TO_POINT = .3

class robot:

    # Number of points from the path to consider for distance
    # (to keep the bot from getting confused)
    numPathPts = 20

    class Mode(Enum):
        STILL = 0
        ROTATING = 1
        LINE_FOLLOW = 2

    ### Fields:
    # pos : (real,real) - the position of the bot on the grid
    # rot : (real,real) - the orientation of bot as XY accelerations (scaled to -1 to 1)
    # path : (real,real) array - the list of points on the path
    # rotTarget : real - angle to rotate to
    # mode : mode_enum - what the current mode should be
    # lineSpeed : real - result of linePID, which is like angular speed
    # angSpeed : real - result of rotPID, which is actually angular speed
    # motor : (real,real) - the values to drive the motor (-1 to 1 for each motor)

    def __init__(self, pos = None, rot=None, path=None, rotTarget=None,
                 mode=Mode.STILL):
        self.pos = pos
        self.rot = rot
        self.path = path
        self.rotTarget = rotTarget
        self.mode = mode

        self.lineSpeed = 0
        self.angSpeed = 0
        self.motor = (0,0)

        self.start_point_index = 0

        # Class to do the bluetooth
        self.bt = wrapper.bt()

        # PID to do line following
        self.linePID = PID.PID(0.01, 0, 0)

        # PID to do rotating to an angle
        self.rotPID = PID.PID(0, 0, 0)

    def setPos(self, pos):
        self.pos = pos
    def setPath(self, path):
        self.start_point_index = 0
        self.path = path

    # update should be called at a regular interval
    # (derivative should be wrt time, so needs a constant delta-T)
    def update(self, pos):
        if(pos != None):
            self.pos = pos

        self.updateRot()

        if self.mode == self.Mode.LINE_FOLLOW:
            self.lineSpeed = self.linePID.update(self.getDistance())
        elif self.mode == self.Mode.ROTATING:
            self.angSpeed = self.rotPID.update(self.anglify(self.rot))

        self.updateMotors()

    def updateRot(self):
        inp = self.bt.read_last()
        if inp != None:
            self.rot = ((inp[1] + 337 - ROTATION_MID), # 337 because that's what we sub'd in the arduino
                        (inp[0] + 337 - ROTATION_MID))

    def changeMode(self, newMode):
        self.mode = newMode
        if newMode == self.Mode.LINE_FOLLOW:
            self.linePID.setPoint(0)
        elif newMode == self.Mode.ROTATING:
            self.rotPID.setPoint(self.rotTarget)


    # Return (Lspeed,Rspeed) based on the current mode
    def getMotors(self):
        # TODO: make the numbers actually make sense
        if self.mode == self.Mode.STILL:
            res = (0,0)
        elif self.mode == self.Mode.ROTATING:
            res = (angSpeed, -angSpeed)
        elif self.mode == self.Mode.LINE_FOLLOW:
            res = (0.1+self.lineSpeed, 0.1-self.lineSpeed) # or something like that
        else:
            print("[ERROR] literally the mode isn't a mode")
            return None

        return (clip(res[0],-1,1), clip(res[1],-1,1))

    def updateMotors(self):
        lm, rm = self.getMotors()
        
        lb = binary_repr(int(lm*(64-0.001)), width=7) # for DEEP and MEANINGFUL reasons
        rb = binary_repr(int(rm*(64-0.001)), width=7)
        self.bt.write(int("0"+lb, 2))
        self.bt.write(int("1"+rb, 2))
        
    def smoothPath(self):
        self.path = pathSmooth(self.path)


    def followLine(self, path=None):
        if path != None:
            self.setPath(path)
            self.smoothPath()
        self.changeMode(self.Mode.LINE_FOLLOW)
        
    def rotateTo(self, angle=None):
        if angle != None:
            self.rotTarget = angle
        self.changeMode(self.Mode.ROTATING)

    def stop(self):
        self.changeMode(self.Mode.STILL)

    # getDistance : void -> real
    def getDistance(self):
        cut_path_end_index = min(self.start_point_index + self.numPathPts,len(self.path))
        if(cut_path_end_index <= self.start_point_index): self.stop

        cutPath = self.path[self.start_point_index:cut_path_end_index]

        d,shortest_distance_to_point,shortest_point_index = distance(self.pos, cutPath, self.rot)

        if (shortest_distance_to_point < MAX_CLOSE_TO_POINT 
            and shortest_point_index > 3):
            self.start_point_index += shortest_point_index - 3

        print("distance to line:", d)
        return d


    def anglify(self, rot):
        # TODO
        return math.atan2(rot[1],rot[0])
