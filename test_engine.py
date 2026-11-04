import unittest
from dataclasses import replace
from unittest.mock import Mock
from engine import Engine, Hand, Settings


def hand(**changes):
    return replace(Hand((.5,.5),(.5,.6),.25,(True,False,False,False),1.0,.4),**changes)


class EngineTests(unittest.TestCase):
    def setUp(self):
        self.sink = Mock()
        self.sink.position.return_value = (960,540)
        self.settings = Settings()
        self.engine = Engine(self.sink,self.settings,(1920,1080))
        self.engine.toggle()

    def feed(self,sample,start,end):
        for i in range(round((end-start)*30)+1):
            self.engine.update(sample,start+i/30)

    def test_paused_never_clicks(self):
        self.engine.toggle()
        self.feed(hand(),0,3)
        self.sink.click.assert_not_called()

    def test_rest_clicks_once_until_cursor_moves(self):
        self.feed(hand(),0,4)
        self.sink.click.assert_called_once_with('left')
        self.sink.move.assert_not_called()

    def test_moving_pointer_does_not_dwell_click(self):
        for i in range(60):
            self.engine.update(hand(point=(.2+i*.004,.5)),i/30)
        self.sink.click.assert_not_called()
        self.sink.move.assert_called()

    def test_reposition_pose_keeps_cursor_still(self):
        self.feed(hand(),0,.4)
        self.feed(hand(fingers=(False,False,False,False)),.45,.7)
        self.engine.update(hand(point=(.8,.8)),.75)
        self.engine.update(hand(point=(.8,.8)),.95)
        self.sink.move.assert_not_called()

    def test_scroll_only_moves_on_stroke(self):
        sample = hand(fingers=(True,True,False,False))
        self.feed(sample,0,.3)
        for i in range(1,11):
            self.engine.update(replace(sample,scroll_y=.4-i*.005),.3+i/30)
        self.sink.wheel.assert_called()
        self.assertTrue(all(c.args[0]>0 for c in self.sink.wheel.call_args_list))
        self.sink.wheel.reset_mock()
        self.feed(replace(sample,scroll_y=.35),.7,2)
        self.sink.wheel.assert_not_called()
        self.sink.click.assert_not_called()
        self.sink.move.assert_not_called()

    def test_scroll_jitter_does_not_move_page(self):
        for i in range(90):
            self.engine.update(hand(fingers=(True,True,False,False),scroll_y=.4+(-1)**i*.001),i/30)
        self.sink.wheel.assert_not_called()

    def test_middle_tap_right_click_fires_once_while_held(self):
        self.feed(hand(),0,.2)
        self.feed(hand(right_gap=.15),.3,2)
        self.sink.click.assert_called_once_with('right')
        self.sink.move.assert_not_called()
        self.sink.down.assert_not_called()

    def test_right_tap_rearms_after_clear_release(self):
        self.feed(hand(),0,.2)
        self.feed(hand(right_gap=.15),.3,.5)
        self.feed(hand(),.6,.8)
        self.feed(hand(right_gap=.15),.9,1.1)
        self.assertEqual(self.sink.click.call_count,2)
        self.assertTrue(all(c.args == ('right',) for c in self.sink.click.call_args_list))

    def test_brief_right_contact_noise_is_ignored(self):
        self.feed(hand(),0,.2)
        self.engine.update(hand(right_gap=.15),.3)
        self.feed(hand(),.33,.5)
        self.sink.click.assert_not_called()

    def test_right_tap_does_not_become_left_pinch(self):
        self.settings.click_mode = 'Pinch'
        self.feed(hand(),0,.2)
        self.feed(hand(right_gap=.1,gap=.3),.3,.6)
        self.feed(hand(),.7,.9)
        self.sink.click.assert_called_once_with('right')
        self.sink.down.assert_not_called()

    def test_left_pinch_does_not_trigger_right_click(self):
        self.settings.click_mode = 'Pinch'
        self.feed(hand(),0,.2)
        self.feed(hand(gap=.1,right_gap=.3),.3,.6)
        self.feed(hand(),.7,.9)
        self.sink.click.assert_not_called()
        self.sink.down.assert_called_once()

    def test_right_tap_does_not_select_menu_with_dwell(self):
        self.feed(hand(),0,.2)
        self.feed(hand(right_gap=.15),.3,.6)
        self.feed(hand(),.7,3)
        self.sink.click.assert_called_once_with('right')

    def test_hand_loss_releases_drag(self):
        self.engine.dragging = True
        self.engine.update(None,0)
        self.sink.up.assert_called_once()
        self.assertFalse(self.engine.dragging)

    def test_pinching_is_not_required_in_rest_mode(self):
        self.feed(hand(gap=.1),0,2)
        self.sink.click.assert_called_once_with('left')
        self.sink.down.assert_not_called()

    def test_pinch_requires_open_before_contact(self):
        self.settings.click_mode = 'Pinch'
        self.feed(hand(gap=.1),0,.3)
        self.sink.down.assert_not_called()
        self.feed(hand(),.4,.6)
        self.feed(hand(gap=.1),.7,1)
        self.sink.down.assert_called_once()

    def test_pinch_press_release_standard_click(self):
        self.settings.click_mode = 'Pinch'
        self.feed(hand(),0,.3)
        self.feed(hand(gap=.1),.4,.7)
        self.feed(hand(),.8,1)
        self.sink.down.assert_called_once()
        self.sink.up.assert_called_once()
        self.sink.move.assert_not_called()
        self.sink.click.assert_not_called()

    def test_single_frame_pinch_is_ignored(self):
        self.settings.click_mode = 'Pinch'
        self.feed(hand(),0,.3)
        self.engine.update(hand(gap=.1),.4)
        self.feed(hand(),.43,.7)
        self.sink.down.assert_not_called()

    def test_pause_releases_pressed_pinch(self):
        self.settings.click_mode = 'Pinch'
        self.feed(hand(),0,.3)
        self.feed(hand(gap=.1),.4,.7)
        self.engine.toggle()
        self.sink.up.assert_called_once()

    def test_camera_gap_resets_scroll_instead_of_jumping(self):
        sample = hand(fingers=(True,True,False,False))
        self.feed(sample,0,.3)
        self.engine.update(replace(sample,scroll_y=.1),1)
        self.engine.update(replace(sample,scroll_y=.1),1.2)
        self.sink.wheel.assert_not_called()

    def test_drag_dwell_has_start_and_drop(self):
        self.engine.next_action = 'drag'
        self.feed(hand(),0,1.3)
        self.sink.down.assert_called_once()
        self.feed(hand(point=(.53,.5)),1.4,3.5)
        self.sink.up.assert_called_once()
        self.assertFalse(self.engine.dragging)


if __name__ == '__main__':
    unittest.main()
