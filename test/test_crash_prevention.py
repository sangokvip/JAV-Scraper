from unittest.mock import MagicMock, patch
from gui.controller import ImageLoadWorker

def test_image_load_worker_signals_finished():
    worker = ImageLoadWorker(
        filepath="/path/to/video.mp4",
        url="http://example.com/image.jpg",
        proxies=None
    )
    
    # Mock signals
    worker.signals = MagicMock()
    
    with patch("gui.controller.requests.get") as mock_get:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = b"fake image bytes"
        mock_get.return_value = mock_response
        
        worker.run()
        
        # 确保加载信号被发射
        worker.signals.loaded.emit.assert_called_once_with(
            "/path/to/video.mp4",
            "http://example.com/image.jpg",
            b"fake image bytes",
            False
        )
        # 确保销毁信号被发射，实现内存安全回收
        worker.signals.finished_worker.emit.assert_called_once_with(worker)
