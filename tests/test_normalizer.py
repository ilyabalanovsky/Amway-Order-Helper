from services.normalizer import clean_name, normalize_name, strip_patronymic


def test_normalize_name_collapses_spaces_and_yo() -> None:
    assert normalize_name("  Ёлкина   Анна   ") == "елкина анна"


def test_clean_name_preserves_original_letters() -> None:
    assert clean_name("  Мария   Ёлкина ") == "Мария Ёлкина"


def test_strip_patronymic_removes_middle_name() -> None:
    assert strip_patronymic("Надежда Юрьевна Меняйленко") == "Надежда Меняйленко"
    assert strip_patronymic("Наталья Анатольевна Россик") == "Наталья Россик"
