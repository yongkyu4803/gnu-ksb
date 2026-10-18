# ProtInteract 실행·검증 안내

UniProt 서열을 조회하여 AlphaFold Server 업로드용 JSON을 만드는 독립 FastAPI 앱입니다.

## 실행

Python 3.11 이상에서 레포를 클론하고 가상환경을 만든 뒤 설치합니다.

```bash
python -m pip install .
python -m uvicorn protinteract.main:app --host 127.0.0.1 --port 8000
```

앱은 `/`, 이 문서 페이지는 `/docs`, API 문서는 `/api/docs`입니다. 상세 OS별 설치법은 저장소 루트 README에 있습니다.

## 검증

```bash
python -m pip install -e ".[dev]"
python -m pytest
```

단위·API 테스트는 외부 통신을 모의 처리합니다. `tests/browser_check.py`는 실행 중인 앱에서 실제 UniProt 조회·JSON 다운로드·입력 변경 방지·모바일 화면을 점검합니다. `python -m playwright install chromium` 후 실행하세요.

실제 AlphaFold Server의 수동 임포트는 미확인입니다. 원본 레포나 로컬 전용 폴더 없이 설치할 수 있고 문서·폰트·화면도 패키지에 포함됩니다.

## 폰트

본문은 앱에 포함된 Pretendard Medium을 사용합니다. 제목은 기계연구원체가 설치되어 있으면 해당 폰트를 사용하고, 없으면 Pretendard로 대체합니다.

[사용 방법](docs/USAGE.md) · [원본 대비 변경사항](CHANGES_FROM_ORIGINAL.md)
