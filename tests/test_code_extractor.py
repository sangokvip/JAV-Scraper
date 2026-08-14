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


def test_amateur_numeric_prefix():
    assert extract_code("259LUXU-1234.mp4") == "259LUXU-1234"
    assert extract_code("300mium_123.mp4") == "300MIUM-123"
    assert extract_code("200GANA-2156.mp4") == "200GANA-2156"


def test_carib_1pondo():
    assert extract_code("123115-001.mp4") == "123115-001"       # 加勒比
    assert extract_code("010112_001.mp4") == "010112_001"       # 一本道
    assert extract_code("[无码]093021_539.mp4") == "093021_539"


def test_tokyo_hot_anchored():
    assert extract_code("n1234.mp4") == "n1234"
    assert extract_code("k0987.mp4") == "k0987"
    # 非开头位置不认，防误伤
    assert extract_code("token1234abc.mp4") != "n1234"


def test_heydouga():
    assert extract_code("heydouga-4017-257.mp4") == "HEYDOUGA-4017-257"


def test_dmm_leading_zero_stripped():
    assert extract_code("ssis00123.mp4") == "SSIS-123"
    assert extract_code("mide00777.mp4") == "MIDE-777"
    # 真实带零番号不受影响
    assert extract_code("ABP-001.mp4") == "ABP-001"


def test_chinese_sub_no_separator():
    assert extract_code("SSIS-001ch.mp4") == "SSIS-001"


def test_no_code():
    assert extract_code("随便一个文件.mp4") is None
    assert extract_code("") is None
