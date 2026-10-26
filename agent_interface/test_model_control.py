import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import model_control as mc

class ModelControlTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.state = patch.object(mc, 'STATE', Path(self.temp.name)/'state.json')
        self.state.start()
        self.addCleanup(self.state.stop)
        mc.CHATS = 0

    def test_invalid_model_cannot_start(self):
        with patch.object(mc,'catalog',return_value={'gemma':{}}), patch.object(mc.threading,'Thread') as thread:
            with self.assertRaises(ValueError): mc.switch('not-installed',lambda:[])
            thread.assert_not_called()

    def test_switch_refuses_chat_or_gpu_run(self):
        with patch.object(mc,'catalog',return_value={'gemma':{}}), patch.object(mc,'status',return_value={'phase':'ready','ready':True,'selected':'qwen'}), patch.object(mc.threading,'Thread') as thread:
            mc.CHATS = 1
            with self.assertRaises(ValueError): mc.switch('gemma',lambda:[])
            mc.CHATS = 0
            with self.assertRaises(ValueError): mc.switch('gemma',lambda:[{'status':'running'}])
            thread.assert_not_called()

    def test_noop_preserves_ready_model(self):
        state={'phase':'ready','ready':True,'selected':'gemma'}
        with patch.object(mc,'catalog',return_value={'gemma':{}}), patch.object(mc,'status',return_value=state), patch.object(mc.threading,'Thread') as thread:
            self.assertEqual(mc.switch('gemma',lambda:[]), state)
            thread.assert_not_called()

    def test_switch_blocks_chat_and_runs(self):
        mc.write_state({'phase':'switching'})
        with self.assertRaises(ValueError): mc.check_run_allowed()
        with patch.object(mc,'status',return_value={'ready':False}):
            with self.assertRaises(ValueError): mc.begin_chat()
        self.assertEqual(mc.CHATS,0)

    def test_restart_makes_interrupted_switch_recoverable(self):
        mc.write_state({'phase':'switching','target':'qwen'})
        mc.recover()
        self.assertIn('failed',mc.STATE.read_text())
        mc.check_run_allowed()

if __name__=='__main__': unittest.main()
