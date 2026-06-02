import pytest
from lib.code_extractor import extract_code

def test_extract_code():
    # 标准有横杠
    assert extract_code("[1080p]SSIS-123_ch.mp4") == "SSIS-123"
    # 无横杠自动补横杠并转大写
    assert extract_code("ipx099.mkv") == "IPX-099"
    # FC2 特殊前缀
    assert extract_code("FC2-PPV-1234567.mp4") == "FC2-PPV-1234567"
    # 排除网址广告前缀误报
    assert extract_code("hhd800.com@MRSS-187.mp4") == "MRSS-187"
    # 孤立数字不匹配
    assert extract_code("123.mp4") is None
    # 匹配不到返回 None
    assert extract_code("random_filename_without_code.mp4") is None
    # 中文字幕 C 后缀自动识别并滤除
    assert extract_code("CESD194C.mp4") == "CESD-194"
    assert extract_code("ABP-123c.mp4") == "ABP-123"
