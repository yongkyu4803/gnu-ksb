# gnu-ksb / ProtInteract

UniProt ID로 단백질 서열을 조회하고 타겟·후보 조합을 **AlphaFold Server 업로드용 JSON**으로 만드는 독립 FastAPI 앱입니다. Python 3.11 이상만 필요하며 Node.js·Streamlit·GPU·API 키는 필요하지 않습니다. UniProt 조회에는 인터넷이 필요합니다.

## 설치·실행

### macOS / Linux

```bash
git clone https://github.com/yongkyu4803/gnu-ksb.git
cd gnu-ksb
python3 -m venv .venv
source .venv/bin/activate
python -m pip install .
python -m uvicorn protinteract.main:app --host 127.0.0.1 --port 8000
```

### Windows PowerShell

```powershell
git clone https://github.com/yongkyu4803/gnu-ksb.git
cd gnu-ksb
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install .
.\.venv\Scripts\python.exe -m uvicorn protinteract.main:app --host 127.0.0.1 --port 8000
```

- 앱: <http://127.0.0.1:8000>
- 문서: <http://127.0.0.1:8000/docs>
- API 문서: <http://127.0.0.1:8000/api/docs>

개발할 때는 `python -m pip install -e ".[dev]"`로 설치하고 서버 명령 끝에 `--reload`를 붙입니다. 일반 설치에도 화면·폰트·문서가 패키지에 포함되므로 원본 레포나 특정 작업 폴더에 의존하지 않습니다. 기본 실행은 로컬 접속용입니다.

## 빠른 사용

1. 타겟에 `P04637 1`을 입력합니다. 복제수를 생략하면 1입니다.
2. 후보에 `Q00987`과 `P04637-2`를 줄바꿈으로 입력합니다.
3. 미리보기를 만들고 서열·생물종·최종 복제수·제외 사유를 확인합니다.
4. JSON을 다운로드하여 AlphaFold Server에 직접 임포트합니다.

잘못된 후보는 제외하고 정상 후보는 계속 처리합니다. 타겟 조회가 실패하면 생성하지 않습니다. 미리보기 후 입력을 바꾸면 이전 다운로드는 무효화됩니다.

## 구현 범위

- canonical·isoform 서열 및 메타데이터 조회, 캐시·강제 재조회
- 복합체·복제수, 동일 대상 합산, 후보별 잡 조합
- 빈 서열·길이 불일치·비정상 FASTA·isoform 불일치 차단
- 표준 아미노산 20종, 최소 4잔기, 복제수 포함 최대 5,000 토큰 검증
- 후보별 포함·제외 사유, 전체 서열 확인, 고유 잡 이름, JSON 다운로드
- Protein Lab 스타일 화면, 모바일 대응, 문서·변경사항 열람

배치 분할·CSV/엑셀 입력·구조 분석·자동 제출·결과 다운로드는 포함하지 않습니다.

## 테스트

```bash
python -m pip install -e ".[dev]"
python -m pytest
```

단위·API 테스트는 외부 통신을 mock합니다. 실행 중인 서버와 실제 UniProt를 확인하는 별도 점검:

```bash
python -m playwright install chromium
python tests/browser_check.py
```

macOS/Linux에서 설치된 Chrome을 사용하려면 `BROWSER_CHANNEL=chrome python tests/browser_check.py`로 실행합니다. 서버 주소는 `APP_URL` 환경변수로 지정할 수 있습니다.

## 제한과 검증 범위

한 요청에 타겟·후보 각각 최대 100개를 순차 조회하며, 요청별 timeout은 20초입니다. 캐시 자동 만료는 없고 체크를 해제하면 새로 조회합니다. 실제 AlphaFold Server 계정의 수동 임포트·수락은 미확인입니다. macOS의 로컬 실행·API·브라우저 동작을 확인했으며 Windows 실제 실행은 미검증입니다.

TLS 인증서 환경변수 `REQUESTS_CA_BUNDLE`·`SSL_CERT_FILE`에 잘못된 경로가 설정되어 있으면 올바르게 수정하거나 해제하세요. 인증서 검증을 끄지 않습니다.

## 출처와 포함한 파일

[mil0608012/AI_vive_coding_KSB](https://github.com/mil0608012/AI_vive_coding_KSB)의 `b05b7d9`를 바탕으로 서열 조회·잡 생성 코어를 재사용·보완했습니다. FastAPI와 정적 웹 화면, 테스트, 설치 설정은 별도로 구성했습니다. 원본 Git 이력, Streamlit 화면, 연구 기획서·피드백, 검토용 장기 계획, 캐시와 개인 환경은 가져오지 않았습니다. 원본 코드의 권리 관계를 변경하거나 새 포괄 라이선스를 부여하지 않습니다.

본문 Pretendard Medium은 포함된 [OFL 라이선스](protinteract/web/fonts/Pretendard-LICENSE.txt)를 따릅니다. 제목 기계연구원체는 설치된 폰트를 사용하며 미설치 시 Pretendard로 대체합니다. 측정·예측 그래프나 가상 연구 데이터는 포함하지 않습니다.

더 자세한 내용은 앱의 Docs 또는 [사용 안내](protinteract/manual/docs/USAGE.md)를 참고하세요.
