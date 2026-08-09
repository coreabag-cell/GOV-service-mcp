"""
정부24_대한민국 공공서비스 정보 OpenAPI -> MCP 래퍼 서버

data.go.kr이 제공하는 "대한민국 공공서비스(혜택) 정보"(정부24 gov24 v3, 보조금24
연계) API를 MCP 도구로 감싼 독립 원격 서버입니다. K-apt(공동주택관리정보)
서버와는 완전히 무관한 도메인이므로 별도 서버/별도 커넥터로 분리했습니다.

배포: Render (Web Service, Python)
전송 방식: Streamable HTTP
인증: GOV_BENEFITS_SERVICE_KEY 환경변수

API 스펙 [확정 — Swagger UI 스크린샷 기준, 2026-08 확인]
---------------------------------------------------------
이 API는 구형 apis.data.go.kr이 아니라 신형 odcloud.kr(공공데이터 API 3.0)
방식입니다. 아래 3개 엔드포인트 모두 파라미터까지 확정되었습니다.

- Base URL: https://api.odcloud.kr/api
- GET /gov24/v3/serviceList        공공서비스 목록
    page, perPage, returnType,
    cond[서비스명::LIKE], cond[소관기관명::LIKE], cond[소관기관유형::LIKE],
    cond[사용자구분::LIKE], cond[서비스분야::LIKE],
    cond[등록일시::LT/LTE/GT/GTE], cond[수정일시::LT/LTE/GT/GTE]
- GET /gov24/v3/serviceDetail       공공서비스 상세내용
    page, perPage, returnType, cond[서비스ID::EQ]
- GET /gov24/v3/supportConditions   공공서비스 지원조건
    page, perPage, returnType, cond[서비스ID::EQ]
    ("서비스ID"는 공공서비스 고유 식별자)

인증 방식도 odcloud.kr 관례상 아래 둘 중 하나입니다 (이 코드는 우선 쿼리
파라미터 방식을 시도하고, 401이 나면 헤더 방식으로 바꿔야 할 수 있습니다):
  - 쿼리파라미터: ?serviceKey=인증키(인코딩)
  - 헤더: Authorization: Infuser 인증키(인코딩)
"""

import os
import httpx
from mcp.server.fastmcp import FastMCP

SERVICE_KEY = os.environ.get("GOV_BENEFITS_SERVICE_KEY", "")
PORT = int(os.environ.get("PORT", 8000))
BASE_URL = "https://api.odcloud.kr/api"

if not SERVICE_KEY:
    print("[경고] GOV_BENEFITS_SERVICE_KEY 환경변수가 설정되지 않았습니다. API 호출이 실패합니다.")

mcp = FastMCP(
    name="gov-benefits-info",
    stateless_http=True,
    host="0.0.0.0",
    port=PORT,
)


def _check_key() -> str | None:
    if not SERVICE_KEY:
        return (
            "GOV_BENEFITS_SERVICE_KEY가 서버에 설정되어 있지 않습니다. "
            "https://www.data.go.kr 마이페이지에서 인증키를 발급받아 Render 환경변수에 등록해주세요."
        )
    return None


async def _call(path: str, params: dict) -> str:
    params = {k: v for k, v in params.items() if v is not None}
    params["serviceKey"] = SERVICE_KEY
    async with httpx.AsyncClient(timeout=20.0) as client:
        try:
            resp = await client.get(f"{BASE_URL}{path}", params=params)
            resp.raise_for_status()
        except httpx.HTTPStatusError as e:
            return (
                f"공공서비스 API 오류 (status {e.response.status_code}): {e.response.text[:500]}\n"
                "※ 401/403이면 인증 방식이 쿼리파라미터가 아니라 헤더(Authorization: Infuser ...)"
                "일 수 있습니다."
            )
        except httpx.RequestError as e:
            return f"공공서비스 API 요청 실패: {e}"
    return resp.text


@mcp.tool()
async def search_gov_services(
    keyword: str | None = None,
    agency_name: str | None = None,
    agency_type: str | None = None,
    user_type: str | None = None,
    service_field: str | None = None,
    page: int = 1,
    per_page: int = 20,
) -> str:
    """[확정] 대한민국 공공서비스(정부 혜택) 목록을 검색합니다.

    정부 부처·지자체·공공기관·교육청이 제공하는 수혜 서비스 목록을 조회합니다.
    강남N168 관리사무소 실무 관점에서는 관리비 지원, 노인정/커뮤니티시설 관련
    지원사업, 에너지 효율화 지원사업 등을 검색하는 용도로 쓸 수 있습니다.

    Args:
        keyword: 서비스명 검색 키워드 (부분일치). 예: "에너지 효율", "공동주택"
        agency_name: 소관기관명 검색 키워드 (부분일치). 예: "국토교통부"
        agency_type: 소관기관유형 검색 키워드 (부분일치). 예: "지자체", "중앙행정기관"
        user_type: 사용자구분 검색 키워드 (부분일치). 예: "개인", "법인"
        service_field: 서비스분야 검색 키워드 (부분일치). 예: "주거·자립"
        page: 페이지 번호 (기본 1)
        per_page: 페이지당 결과 수 (기본 20)
    """
    key_error = _check_key()
    if key_error:
        return key_error
    params = {"page": page, "perPage": per_page}
    if keyword:
        params["cond[서비스명::LIKE]"] = keyword
    if agency_name:
        params["cond[소관기관명::LIKE]"] = agency_name
    if agency_type:
        params["cond[소관기관유형::LIKE]"] = agency_type
    if user_type:
        params["cond[사용자구분::LIKE]"] = user_type
    if service_field:
        params["cond[서비스분야::LIKE]"] = service_field
    return await _call("/gov24/v3/serviceList", params)


@mcp.tool()
async def get_gov_service_detail(service_id: str) -> str:
    """[확정] 특정 공공서비스의 상세내용을 조회합니다.

    search_gov_services로 찾은 서비스의 ID를 넣어 상세 설명, 신청 방법, 지원
    내용 등을 조회합니다.

    Args:
        service_id: 공공서비스 고유 식별자(서비스ID). search_gov_services 응답의
                    서비스ID 필드값을 그대로 넣으면 됩니다.
    """
    key_error = _check_key()
    if key_error:
        return key_error
    params = {"page": 1, "perPage": 1, "cond[서비스ID::EQ]": service_id}
    return await _call("/gov24/v3/serviceDetail", params)


@mcp.tool()
async def get_gov_service_support_conditions(service_id: str) -> str:
    """[확정] 특정 공공서비스의 지원조건(자격요건)을 조회합니다.

    Args:
        service_id: 공공서비스 고유 식별자(서비스ID)
    """
    key_error = _check_key()
    if key_error:
        return key_error
    params = {"page": 1, "perPage": 1, "cond[서비스ID::EQ]": service_id}
    return await _call("/gov24/v3/supportConditions", params)


if __name__ == "__main__":
    mcp.run(transport="streamable-http")
