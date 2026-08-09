# gov-benefits-mcp — 대한민국 공공서비스(혜택) 정보 → MCP 래퍼

행정안전부가 data.go.kr을 통해 제공하는 "대한민국 공공서비스(혜택) 정보"
(정부24 gov24 v3, 보조금24 연계) API를 Claude 커스텀 커넥터에서 사용할 수
있게 감싼 **독립된** 원격 MCP 서버입니다. `kcsc-mcp`, `data-go-kr-housing-mcp`와는
완전히 별개로, K-apt/건설기준 업무와는 무관한 도메인이라 분리했습니다.

## 제공 도구 [전체 확정]

| 도구 | 설명 |
|---|---|
| `search_gov_services` | 공공서비스(혜택) 목록 검색 (`GET /gov24/v3/serviceList`) |
| `get_gov_service_detail` | 서비스 상세내용 조회 (`GET /gov24/v3/serviceDetail`) |
| `get_gov_service_support_conditions` | 지원조건(자격요건) 조회 (`GET /gov24/v3/supportConditions`) |

## 현재 상태

Swagger UI 스크린샷 3장으로 **3개 엔드포인트 전부 파라미터까지 확정**되었습니다.

- Base URL: `https://api.odcloud.kr/api` (신형 odcloud.kr / 공공데이터 API 3.0 방식)
- `serviceList`: `page`, `perPage`, `returnType`,
  `cond[서비스명::LIKE]`, `cond[소관기관명::LIKE]`, `cond[소관기관유형::LIKE]`,
  `cond[사용자구분::LIKE]`, `cond[서비스분야::LIKE]`,
  `cond[등록일시::LT/LTE/GT/GTE]`, `cond[수정일시::LT/LTE/GT/GTE]`
- `serviceDetail`, `supportConditions`: `page`, `perPage`, `returnType`,
  `cond[서비스ID::EQ]`
  → 필드명이 영문 코드가 아니라 **한글 그대로**라는 점이 특이점입니다.

남은 것은 실제 인증키로 호출했을 때 인증 방식(쿼리파라미터 vs 헤더)이
맞는지 확인하는 것뿐입니다 — 아래 "인증 실패 시 체크리스트" 참고.

## 1단계 — 인증키 발급

1. https://www.data.go.kr → "대한민국 공공서비스(혜택) 정보" 검색 → 활용신청 (자동승인)
2. 마이페이지에서 인증키(일반 인증키) 확인
   - 다만 odcloud.kr 계열은 **"인증키 설정"** 버튼(스크린샷 우측 상단 초록 자물쇠)에서
     별도로 활성화가 필요할 수 있습니다 — Swagger 페이지에서 "인증키 설정" 클릭 후
     안내에 따라주세요.

## 2단계 — Render에 배포

1. `server.py`, `requirements.txt`, `README.md`를 새 GitHub 레포 루트에 업로드
   (K-apt 서버와 반드시 **다른 레포**로 분리하세요)
2. Render → New → Web Service → 레포 선택
   - Build Command: `pip install -r requirements.txt`
   - Start Command: `python server.py`
3. Environment Variables:
   - `GOV_BENEFITS_SERVICE_KEY` = 1단계에서 발급받은 인증키

## 3단계 — Claude 커스텀 커넥터 등록

1. Claude.ai → Settings → Connectors → **+ Add custom connector**
2. Name: `공공서비스 혜택정보` 등
3. URL: `https://<서비스이름>.onrender.com/mcp`
4. OAuth Client ID/Secret은 비워두세요

## 로컬 테스트

```bash
python -m venv venv
./venv/bin/pip install -r requirements.txt
GOV_BENEFITS_SERVICE_KEY=발급받은키 PORT=8126 ./venv/bin/python server.py
```

다른 터미널:
```bash
curl -N -X POST http://127.0.0.1:8126/mcp/ \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-06-18","capabilities":{},"clientInfo":{"name":"test","version":"1.0"}}}'
```
`serverInfo.name: "gov-benefits-info"` 가 포함된 응답이 오면 정상입니다.

## 인증 실패(401/403) 시 체크리스트 [요확인]

odcloud.kr 계열 API는 인증 방식이 두 가지로 갈립니다. `search_gov_services`
호출 시 401/403이 나면:

1. 쿼리파라미터 `serviceKey=인코딩된키` 방식이 아니라 **헤더**
   `Authorization: Infuser 인코딩된키` 방식일 수 있습니다 — 이 경우 알려주시면
   `_call()` 함수를 헤더 방식으로 바꿔드립니다.
2. 스크린샷 우측 상단의 **"인증키 설정"** 버튼을 눌러 해당 API 전용으로
   키를 별도 등록해야 할 수도 있습니다 (odcloud.kr은 서비스별로 이 설정이
   필요한 경우가 있습니다).
