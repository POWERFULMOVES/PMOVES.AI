import asyncio
import json
import unittest
from unittest.mock import AsyncMock, patch

# Import the consumer script
import cgp_consumer

class TestCGPConsumer(unittest.IsolatedAsyncioTestCase):
    @patch("cgp_consumer.NATS")
    async def test_message_handler(self, mock_nats_cls):
        mock_nc = AsyncMock()
        mock_nats_cls.return_value = mock_nc
        
        # We need to capture the message handler.
        # Let's extract the translation logic from main by mocking subscribe.
        handler = None
        async def mock_subscribe(subject, cb):
            nonlocal handler
            handler = cb
            
        mock_nc.subscribe.side_effect = mock_subscribe
        
        # Start the main loop as a task and cancel it soon after so it registers the handler
        main_task = asyncio.create_task(cgp_consumer.main())
        await asyncio.sleep(0.1) # Let the handler register
        
        self.assertIsNotNone(handler)
        
        # Create a mock message
        class MockMsg:
            def __init__(self, subject, data):
                self.subject = subject
                self.data = data
                
        test_payload = {
            "spec": "chit.cgp.v0.2",
            "type": "geometry.health.v1",
            "super_nodes": [{"id": "sn1"}],
            "control_plane": {
                "param_surface": {
                    "suit_id": "mr_clean",
                    "temperature": 0.1
                }
            }
        }
        
        msg = MockMsg("geometry.cgp.v1", json.dumps(test_payload).encode())
        
        # Feed it to the handler
        await handler(msg)
        
        # Verify publish was called
        mock_nc.publish.assert_called_once()
        args, _ = mock_nc.publish.call_args
        
        pub_subject = args[0]
        pub_data = json.loads(args[1].decode())
        
        self.assertEqual(pub_subject, "geometry.packet.decoded.v1")
        self.assertEqual(pub_data["source_spec"], "chit.cgp.v0.2")
        self.assertEqual(pub_data["control_plane"]["param_surface"]["suit_id"], "mr_clean")
        self.assertEqual(pub_data["control_plane"]["param_surface"]["temperature"], 0.1)
        
        main_task.cancel()

if __name__ == "__main__":
    unittest.main()
