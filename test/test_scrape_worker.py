from unittest.mock import MagicMock, patch
from gui.scrape_worker import ScrapeWorker

def test_scrape_worker_normal_path_filters_magnets():
    # 测试普通文件导入：应将 magnets 置空
    worker = ScrapeWorker(
        file_path="/path/to/imported_video.mp4",
        code="ABP-123",
        output_dir="/output",
        platform="javdb",
        only_scrape=True
    )
    
    mock_detail = {
        "code": "ABP-123",
        "title": "Test Title",
        "magnets": [
            {"magnet": "magnet:?xt=urn:btih:1", "size_text": "1.5GB"},
            {"magnet": "magnet:?xt=urn:btih:2", "size_text": "2.1GB"}
        ],
        "cover_url": "http://example.com/cover.jpg",
        "thumbnail_images": []
    }
    
    with patch("gui.scrape_worker.AdapterFactory") as mock_factory:
        mock_adapter = MagicMock()
        mock_adapter.get_video_by_code.return_value = mock_detail
        mock_factory.get_adapter_by_name.return_value = mock_adapter
        
        # 拦截信号以防报错
        worker.signals = MagicMock()
        
        # 运行 worker
        worker.run()
        
        # 验证 magnets 是否被成功清空
        assert mock_detail["magnets"] == []
        # 验证信号传递的数据中的 magnets 也为空
        args = worker.signals.preview_loaded.emit.call_args[0]
        assert args[1]["magnets"] == []


def test_scrape_worker_virtual_path_keeps_magnets():
    # 测试手动番号输入：应该保留 magnets 刮削数据
    worker = ScrapeWorker(
        file_path="__virtual__:ABP-123",
        code="ABP-123",
        output_dir="/output",
        platform="javdb",
        only_scrape=True
    )
    
    mock_detail = {
        "code": "ABP-123",
        "title": "Test Title",
        "magnets": [
            {"magnet": "magnet:?xt=urn:btih:1", "size_text": "1.5GB"},
            {"magnet": "magnet:?xt=urn:btih:2", "size_text": "2.1GB"}
        ],
        "cover_url": "http://example.com/cover.jpg",
        "thumbnail_images": []
    }
    
    with patch("gui.scrape_worker.AdapterFactory") as mock_factory:
        mock_adapter = MagicMock()
        mock_adapter.get_video_by_code.return_value = mock_detail
        mock_factory.get_adapter_by_name.return_value = mock_adapter
        
        worker.signals = MagicMock()
        worker.run()
        
        # 验证 magnets 是否完好保留
        assert len(mock_detail["magnets"]) == 2
        assert mock_detail["magnets"][0]["magnet"] == "magnet:?xt=urn:btih:1"
        # 验证信号中的 magnets 保留
        args = worker.signals.preview_loaded.emit.call_args[0]
        assert len(args[1]["magnets"]) == 2
