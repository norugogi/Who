import json
import time
from pathlib import Path

import requests


# =========================================================
# 너 누구야 - 일반 랭킹 + 결사 랭킹 통합 추출기
# 실행하면 같은 폴더에 JSON 2개가 생성됩니다.
#   1) Who_are_you.json
#   2) Who_are_you_guild.json
# =========================================================

BASE_URL = "https://wp-api.nexon.com/v1/GameData"

GC_RANKING_URL = f"{BASE_URL}/gcranking"
GUILD_RANKING_URL = f"{BASE_URL}/guildranking"

HEADERS = {
    "Authorization": "Bearer 3E5C4287-849D-4EAA-A4EB-4528C9AB8E7D",
    "X-Wp-Api-Key": "wp_fe_api_key",
    "Content-Type": "application/json",
    "Origin": "https://wp.nexon.com",
    "Referer": "https://wp.nexon.com/",
}

WORLDS = [
    "2-1", "2-2", "2-3", "2-4", "2-5",
    "3-1", "3-2", "3-3", "3-4", "3-5",
    "5-1", "5-2", "5-3", "5-4", "5-5",
    "8-1", "8-2", "8-3", "8-4", "8-5",
    "10-1", "10-2", "10-3", "10-4", "10-5",
    "11-1", "11-2", "11-3", "11-4", "11-5",
    "12-1", "12-2", "12-3", "12-4", "12-5",
    "14-1", "14-2", "14-3", "14-4", "14-5",
    "16-1", "16-2", "16-3", "16-4", "16-5",
    "27-1", "27-2", "27-3", "27-4", "27-5",
]

OUTPUT_CHARACTER = Path("Who_are_you.json")
OUTPUT_GUILD = Path("Who_are_you_guild.json")

REQUEST_TIMEOUT = 20
REQUEST_DELAY = 0.15
MAX_RETRIES = 3


def make_world_ids(world: str) -> tuple[str, str]:
    server, channel = world.split("-")
    world_group_id = f"LIVE_W{int(server):02d}"
    world_id = f"{world_group_id}_R{channel}"
    return world_group_id, world_id


def safe_int(value, default=0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def request_ranking(
    session: requests.Session,
    url: str,
    payload: dict,
) -> dict:
    last_error = None

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = session.post(
                url,
                json=payload,
                timeout=REQUEST_TIMEOUT,
            )
            response.raise_for_status()

            data = response.json()

            if data.get("code") != "0000":
                raise RuntimeError(
                    f"API 오류: code={data.get('code')}, "
                    f"message={data.get('message')}"
                )

            return data

        except Exception as error:
            last_error = error

            if attempt < MAX_RETRIES:
                print(
                    f"    재시도 {attempt}/{MAX_RETRIES - 1}: {error}"
                )
                time.sleep(1)

    raise RuntimeError(last_error)


def extract_character_ranking(
    data: dict,
    world: str,
    world_group_id: str,
    world_id: str,
) -> list[dict]:
    players = data.get("result", {}).get("gc", [])
    result = []

    for player in players:
        result.append({
            "world": world,
            "world_group_id": world_group_id,
            "world_id": world_id,
            "name": player.get("gc_name"),
            "level": player.get("gc_level"),
            "grade": safe_int(
                player.get("string_map", {}).get("grade", 0)
            ),
            "class": player.get("class"),
            "guild": player.get("guild_name"),
            "ranking": player.get("ranking"),
        })

    return result


def extract_guild_ranking(
    data: dict,
    world: str,
    world_group_id: str,
    world_id: str,
) -> list[dict]:
    guilds = data.get("result", {}).get("guild_ranking", [])
    result = []

    for guild in guilds:
        result.append({
            "world": world,
            "world_group_id": world_group_id,
            "world_id": world_id,
            "ranking": guild.get("ranking"),
            "ranking_change": guild.get("ranking_change"),
            "guild_name": guild.get("guild_name"),
            "guild_master": guild.get("guild_master_sc_name"),
            "guild_level": guild.get("guild_level"),
            "guild_member_count": guild.get("guild_member_count"),
            "max_guild_member_count": guild.get(
                "max_guild_member_count"
            ),
            "territory_flag_id": guild.get(
                "territory_flag_id", []
            ),
            "territory_name": guild.get(
                "territory_name", []
            ),
        })

    return result


def save_json(path: Path, data: list[dict]) -> None:
    with path.open("w", encoding="utf-8") as file:
        json.dump(
            data,
            file,
            ensure_ascii=False,
            indent=2,
        )


def main() -> None:
    all_characters = []
    all_guilds = []

    failed_character_worlds = []
    failed_guild_worlds = []

    print("=" * 58)
    print("너 누구야 - 일반 랭킹 + 결사 랭킹 통합 추출")
    print(f"대상 서버: {len(WORLDS)}개")
    print("=" * 58)

    with requests.Session() as session:
        session.headers.update(HEADERS)

        for index, world in enumerate(WORLDS, start=1):
            world_group_id, world_id = make_world_ids(world)

            payload = {
                "world_group_id": world_group_id,
                "world_id": world_id,
            }

            print(
                f"\n[{index:02d}/{len(WORLDS)}] "
                f"{world} ({world_id})"
            )

            # 일반 랭킹
            try:
                character_data = request_ranking(
                    session,
                    GC_RANKING_URL,
                    payload,
                )

                characters = extract_character_ranking(
                    character_data,
                    world,
                    world_group_id,
                    world_id,
                )

                all_characters.extend(characters)

                print(
                    f"  일반 랭킹 완료: {len(characters):,}명"
                )

            except Exception as error:
                failed_character_worlds.append(world)
                print(f"  일반 랭킹 실패: {error}")

            # 결사 랭킹
            try:
                guild_data = request_ranking(
                    session,
                    GUILD_RANKING_URL,
                    payload,
                )

                guilds = extract_guild_ranking(
                    guild_data,
                    world,
                    world_group_id,
                    world_id,
                )

                all_guilds.extend(guilds)

                print(
                    f"  결사 랭킹 완료: {len(guilds):,}개"
                )

            except Exception as error:
                failed_guild_worlds.append(world)
                print(f"  결사 랭킹 실패: {error}")

            time.sleep(REQUEST_DELAY)

    save_json(OUTPUT_CHARACTER, all_characters)
    save_json(OUTPUT_GUILD, all_guilds)

    print("\n" + "=" * 58)
    print("추출 완료")
    print(f"일반 랭킹: {len(all_characters):,}명")
    print(f"결사 랭킹: {len(all_guilds):,}개")
    print(f"일반 JSON: {OUTPUT_CHARACTER.resolve()}")
    print(f"결사 JSON: {OUTPUT_GUILD.resolve()}")

    if failed_character_worlds:
        print(
            "일반 랭킹 실패 서버:",
            ", ".join(failed_character_worlds),
        )
    else:
        print("일반 랭킹 실패 서버: 없음")

    if failed_guild_worlds:
        print(
            "결사 랭킹 실패 서버:",
            ", ".join(failed_guild_worlds),
        )
    else:
        print("결사 랭킹 실패 서버: 없음")

    print("=" * 58)

    try:
        input("\n엔터를 누르면 종료합니다...")
    except EOFError:
        pass


if __name__ == "__main__":
    main()
