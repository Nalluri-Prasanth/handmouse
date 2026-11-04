"""Hand Mouse Studio: gesture states independent of camera and desktop input."""
from dataclasses import dataclass
import math
from smoothing import OneEuroFilter


@dataclass
class Settings:
    pointer: float = 3.5
    scroll: float = 2.0
    dwell: float = .9
    click_mode: str = 'Rest to click'
    pinch_close: float = .38
    reverse_scroll: bool = False


@dataclass
class Hand:
    point: tuple
    palm: tuple
    scale: float
    fingers: tuple
    gap: float
    scroll_y: float
    right_gap: float = 1.0


def observe(points, aspect):
    def distance(a,b):
        return math.hypot((points[a].x-points[b].x)*aspect,points[a].y-points[b].y)
    scale = max(.04,distance(0,9),distance(5,17))
    palm = tuple(sum(getattr(points[i],axis) for i in (0,5,9,13,17))/5 for axis in ('x','y'))
    fingers = tuple(distance(0,t)>distance(0,j)*1.12 for t,j in ((8,6),(12,10),(16,14),(20,18)))
    point = tuple(.65*getattr(points[8],axis)+.35*palm[i] for i,axis in enumerate(('x','y')))
    return Hand(point,palm,scale,fingers,distance(4,8)/scale,(points[8].y+points[12].y)/2,distance(4,12)/scale)


class Engine:
    def __init__(self, sink, settings, size):
        self.sink,self.settings,self.size = sink,settings,size
        self.paused = True
        self.status = 'Paused — press Start or F8'
        self.progress = 0
        self.dragging = False
        self.next_action = 'left'
        self.reset()

    def reset(self):
        if self.dragging:
            self.sink.up()
        self.dragging = False
        self.reference = None
        self.output = None
        self.filter = OneEuroFilter(1.2,.007)
        self.pose = None
        self.pose_start = 0
        self.dwell_origin = None
        self.dwell_start = None
        self.fired_at = None
        self.scroll_ref = None
        self.scroll_residual = 0
        self.pinch_start = None
        self.pinch_open = None
        self.pinch_origin = None
        self.pinch_armed = False
        self.pinch_down = False
        self.right_fired = False
        self.right_armed = False
        self.right_start = None
        self.right_open = None
        self.last_time = None
        self.progress = 0

    def release(self):
        if self.pinch_down:
            self.sink.up()
            self.pinch_down = False
            self.dragging = False
        self.reset()

    def toggle(self):
        self.release()
        self.paused = not self.paused
        self.status = 'Paused' if self.paused else 'Ready — point with your index finger'

    def mode_changed(self):
        self.release()

    def update(self, hand, now):
        if self.paused or hand is None:
            self.release()
            self.status = 'Paused — F8 to start' if self.paused else 'Hand lost — buttons released'
            return
        if self.last_time is not None and now-self.last_time > .3:
            self.release()
        self.last_time = now
        if self.pinch_start is None and not self.dragging and self.right_tap(hand,now):
            return
        index,middle,ring,little = hand.fingers
        # In pinch mode an existing contact owns input until release.
        pinch = self.settings.click_mode == 'Pinch' and (self.pinch_start is not None or hand.gap < self.settings.pinch_close)
        raw = 'pinch' if pinch else 'scroll' if index and middle and not ring and not little else 'move' if index and not middle else 'rest'
        if raw != self.pose:
            self.pose,self.pose_start = raw,now
            self.reference = None
            self.scroll_ref = None
            self.scroll_residual = 0
            self.dwell_origin = self.dwell_start = None
            self.progress = 0
        if raw != 'pinch' and hand.gap > self.settings.pinch_close+.18:
            self.pinch_armed = True
        if raw == 'pinch':
            self.pinch(hand,now)
            return
        if raw == 'rest':
            if self.dragging:
                self.sink.up()
                self.dragging = False
            self.status = 'Rest — reposition your hand freely'
            return
        if now-self.pose_start < .16:
            self.status = 'Settling gesture…'
            return
        if raw == 'scroll':
            if self.dragging:
                self.sink.up()
                self.dragging = False
            self.scroll(hand)
            self.status = 'Scroll — short strokes; stay still to stop'
        else:
            self.move(hand.point,now)
            self.status = 'Point — rest to click' if self.settings.click_mode == 'Rest to click' else 'Point — pinch and release to click'
            if self.settings.click_mode == 'Rest to click':
                self.dwell(now)

    def right_tap(self, hand, now):
        close = self.settings.pinch_close
        if hand.right_gap > close+.20:
            if self.right_start is None:
                self.right_armed = True
                return False
            if self.right_open is None:
                self.right_open = now
            if now-self.right_open >= .07:
                self.right_start = self.right_open = None
                self.right_fired = False
                self.right_armed = True
                self.pose = None
            return True
        contact = hand.right_gap < close and hand.right_gap+.08 < hand.gap
        if self.right_start is None:
            if not contact or not self.right_armed:
                return False
            self.right_start = now
            self.reference = None
            self.dwell_origin = self.dwell_start = None
            self.scroll_ref = None
            self.scroll_residual = 0
            self.progress = 0
        self.right_open = None
        self.status = 'Middle-finger tap detected…'
        # Ignore one-frame contacts; one click per contact regardless of hold duration.
        if now-self.right_start >= .07 and not self.right_fired:
            self.sink.click('right')
            self.right_fired = True
            self.fired_at = tuple(self.sink.position())
        if self.right_fired:
            self.status = 'Right clicked — separate thumb and middle to re-arm'
        return True

    def move(self, point, now):
        raw = (point[0]*self.size[0]*self.settings.pointer,
               point[1]*self.size[1]*self.settings.pointer*1.25)
        if self.reference is None:
            self.reference = raw
            self.output = tuple(self.sink.position())
            self.origin = self.output
            self.filter.reset()
        target = tuple(self.origin[i]+raw[i]-self.reference[i] for i in (0,1))
        filtered = self.filter(target,now)
        distance = math.dist(self.output,filtered)
        if distance > 2.5:
            ratio = (distance-2.5)/distance
            desired = tuple(self.output[i]+ratio*(filtered[i]-self.output[i]) for i in (0,1))
            clipped = tuple(max(3,min(self.size[i]-4,desired[i])) for i in (0,1))
            correction = tuple(clipped[i]-desired[i] for i in (0,1))
            self.origin = tuple(self.origin[i]+correction[i] for i in (0,1))
            self.filter.x = self.filter.x + correction
            self.output = clipped
            self.sink.move(*map(round,self.output))

    def dwell(self, now):
        if self.output is None:
            return
        if self.fired_at is not None:
            if math.dist(self.fired_at,self.output) < 38:
                self.progress = 0
                self.status = 'Clicked — move to the next target'
                return
            self.fired_at = None
        if self.dwell_origin is None or math.dist(self.dwell_origin,self.output)>16:
            self.dwell_origin,self.dwell_start = self.output,now
        self.progress = min(1,(now-self.dwell_start)/self.settings.dwell)
        if self.progress >= 1:
            if self.dragging:
                self.sink.up()
                self.dragging = False
            elif self.next_action == 'drag':
                self.sink.down()
                self.dragging = True
            elif self.next_action == 'double':
                self.sink.click('double')
            else:
                self.sink.click(self.next_action)
            self.next_action = 'left'
            self.fired_at = self.output
            self.status = 'Dragging — move, then rest again to drop' if self.dragging else 'Clicked'

    def scroll(self, hand):
        if self.scroll_ref is None:
            self.scroll_ref = hand.scroll_y
            return
        delta = (self.scroll_ref-hand.scroll_y)/hand.scale
        if abs(delta)<.015:
            return
        motion = delta-math.copysign(.015,delta)
        self.scroll_ref = hand.scroll_y+math.copysign(.015*hand.scale,delta)
        if motion*self.scroll_residual<0:
            self.scroll_residual = 0
        # Fractional Windows wheel units; 120 units are one wheel notch.
        self.scroll_residual += motion*self.settings.scroll*1500
        wheel = max(-240,min(240,int(self.scroll_residual)))
        if wheel:
            self.sink.wheel(-wheel if self.settings.reverse_scroll else wheel)
            self.scroll_residual -= int(self.scroll_residual)

    def pinch(self, hand, now):
        self.dwell_origin = self.dwell_start = None
        self.progress = 0
        if not self.pinch_armed:
            self.status = 'Open thumb and index first to arm clicking'
            if hand.gap > self.settings.pinch_close+.18:
                self.pinch_start = None
                self.pinch_armed = True
            return
        if self.pinch_start is None:
            self.pinch_start,self.pinch_origin = now,hand.palm
        if hand.gap > self.settings.pinch_close+.18:
            if self.pinch_open is None:
                self.pinch_open = now
            if now-self.pinch_open >= .065:
                if self.pinch_down:
                    self.sink.up()
                self.pinch_down = self.dragging = False
                self.pinch_start = self.pinch_open = None
                self.reference = None
                self.status = 'Released'
            return
        self.pinch_open = None
        if now-self.pinch_start >= .07 and not self.pinch_down:
            self.sink.down()
            self.pinch_down = True
        moved = math.dist(hand.palm,self.pinch_origin)/hand.scale
        if self.pinch_down and moved>.10 and now-self.pinch_start>.18:
            self.dragging = True
        if self.dragging:
            self.move(hand.palm,now)
        self.status = 'Dragging — open fingers to drop' if self.dragging else 'Mouse pressed — open fingers to click'
