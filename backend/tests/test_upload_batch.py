from app.constants import UploadStatus
from app.domain.upload_batch import merge_upload_status, tag_error_message


def test_merge_upload_status():
    assert merge_upload_status([]) == UploadStatus.ERROR.value
    assert merge_upload_status(["success", "success"]) == UploadStatus.SUCCESS.value
    assert merge_upload_status(["error"]) == UploadStatus.ERROR.value
    assert merge_upload_status(["success", "error"]) == UploadStatus.PARTIAL.value
    assert merge_upload_status(["partial", "success"]) == UploadStatus.PARTIAL.value


def test_tag_error_message():
    assert tag_error_message("Пусто") == "Пусто"
    assert tag_error_message("Нет колонок", file_name="a.xlsx", row=3) == "В файле «a.xlsx» в строке 3: Нет колонок"
    assert (
        tag_error_message("Артикул не найден", file_name="b.xlsx", row=4, counterparty="ТОО А")
        == "В файле «b.xlsx» по ТОО А в строке 4: Артикул не найден"
    )
    already = "В файле «a.xlsx» в строке 2: ошибка"
    assert tag_error_message(already, file_name="a.xlsx", row=2) == already
