from lib.code_extractor import extract_code


def test_standard_code():
    assert extract_code("SSIS-001.mp4") == "SSIS-001"
    assert extract_code("ssis001.mp4") == "SSIS-001"
    assert extract_code("MIDA_583.mkv") == "MIDA-583"


def test_fc2_variants():
    assert extract_code("FC2-PPV-1234567.mp4") == "FC2-PPV-1234567"
    assert extract_code("FC2-1234567.mp4") == "FC2-PPV-1234567"
    assert extract_code("fc2ppv_1234567.mp4") == "FC2-PPV-1234567"


def test_t28():
    assert extract_code("T28-633.mp4") == "T28-633"


def test_chinese_sub_suffix_stripped():
    assert extract_code("SSIS-001-C.mp4") == "SSIS-001"
    assert extract_code("SSIS-001-CH.mp4") == "SSIS-001"
    assert extract_code("MIDA-583C.mp4") == "MIDA-583"


def test_ad_domain_stripped():
    assert extract_code("hhd800.com@SSIS-001.mp4") == "SSIS-001"


def test_resolution_tag_stripped():
    assert extract_code("[1080P]SSIS-001.mp4") == "SSIS-001"


def test_no_code():
    assert extract_code("随便一个文件.mp4") is None
    assert extract_code("") is None
