import pytest
from unittest.mock import MagicMock, patch
from gui.scrape_worker import ScrapeWorker

def test_scrape_worker_path_traversal_prevention():
    # 模拟从网络恶意获取到的番号或标题试图写出到非 output 目录
    worker = ScrapeWorker(
        file_path="/path/to/video.mp4",
        code="../../malicious_code",  # 恶意的番号
        output_dir="/Users/mac/Documents/GitHub/ javdb-api-scraper/output",
        platform="javdb",
        only_scrape=False
    )
    
    mock_detail = {
        "code": "../../malicious_code",
        "title": "Title with malicious elements ../../",
        "magnets": [],
        "cover_url": "http://example.com/cover.jpg",
        "thumbnail_images": []
    }
    
    with patch("gui.scrape_worker.AdapterFactory") as mock_factory:
        mock_adapter = MagicMock()
        mock_adapter.get_video_by_code.return_value = mock_detail
        mock_factory.get_adapter_by_name.return_value = mock_adapter
        
        worker.signals = MagicMock()
        
        # 运行 scrape worker
        worker.run()
        
        # 确认 finished 信号携带错误描述，包含 Path Traversal 或安全验证失败信息
        args = worker.signals.finished.emit.call_args[0]
        assert "success" not in args[1]
        assert "安全校验失败" in args[1] or "PermissionError" in args[1]
