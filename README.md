# danbooru-mcp

Claude 같은 MCP 클라이언트에서 [Danbooru](https://danbooru.donmai.us)를 검색하고 이미지를 바로 볼 수 있게 해주는 MCP 서버입니다.

- **파일 하나, 설치할 것 없음** — 파이썬 표준 라이브러리만 씁니다 (Python 3.9+).
- **로컬에 아무것도 저장하지 않음** — 이미지는 디스크에 쓰지 않고 채팅에 바로 표시됩니다.
- **SNI 차단 우회** — 접속 첫 메시지(TLS ClientHello)를 TLS 레코드 두 조각으로 나눠 보내서, 사이트 이름으로 막는 통신사 차단(예: 한국 통신사)에서도 동작합니다.

## 도구

| 도구 | 하는 일 |
|---|---|
| `search_posts` | 태그로 게시물 검색 (`hatsune_miku rating:g order:score` 같은 Danbooru 문법) |
| `get_post` | ID로 게시물 정보·태그 보기 |
| `count_posts` | 태그 조합의 게시물 수 |
| `autocomplete_tags` | 대충 쓴 말이나 별칭에서 정확한 태그명 찾기 |
| `get_image` | 이미지를 채팅에 표시 (`preview` / `sample` ~850px / `original`) |

## 설치

필요한 것: Python 3.9 이상 (`python` 명령으로 실행되어야 합니다).

### 가장 쉬운 방법 — Claude에게 맡기기

Claude Code에 이렇게 말하면 됩니다.

> https://github.com/parkjaehyeon12354/danbooru-mcp 깔아줘

설치가 끝나면 Claude Code를 새 세션으로 다시 열어야 도구가 보입니다.

### 직접 설치 (Claude Code)

```powershell
claude plugin install danbooru --marketplace parkjaehyeon12354/danbooru-mcp
```

Claude Code 안에서는 `/plugin install danbooru --marketplace parkjaehyeon12354/danbooru-mcp`

### 직접 설치 (Claude Desktop)

[`danbooru_mcp.py`](danbooru_mcp.py)를 받아서 원하는 폴더에 둡니다.

`python danbooru_mcp.py --test`를 실행해서 `ok: [...]`가 나오면 연결된 것입니다.

그다음 `%APPDATA%\Claude\claude_desktop_config.json` (macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`)에 아래 내용을 추가하고 앱을 재시작합니다.

```json
{
  "mcpServers": {
    "danbooru": {
      "command": "python",
      "args": ["C:/경로/danbooru-mcp/danbooru_mcp.py"]
    }
  }
}
```

## 사용 예

- "단보루에서 hatsune_miku 점수 높은 순으로 10개 찾아줘"
- "게시물 210001 이미지 보여줘"
- "미쿠 정확한 태그명이 뭐야?"

## 제한과 옵션

- 로그인하지 않으면 한 번에 일반 태그 **2개**까지 조합할 수 있습니다. `rating:g`, `order:score` 같은 메타태그는 개수에 들어가지 않습니다.
### API 키 (선택)

API 키는 **딸려오지 않습니다.** 없어도 모든 기능이 동작하고, 넣으면 제한이 늘어납니다 (Gold 계정은 태그 6개). 키는 Danbooru 계정 설정의 API Keys에서 직접 만듭니다. 자기 키를 남에게 공유하지 마세요.

- **Claude Code 플러그인:** Claude Code 안에서 `/plugin configure danbooru`를 실행해 아이디와 키를 넣고, Claude Code를 다시 시작합니다. 키는 Claude Code의 보안 저장소에 들어갑니다.
  설치할 때 함께 넣을 수도 있습니다.

  ```powershell
  claude plugin install danbooru --marketplace parkjaehyeon12354/danbooru-mcp --config login=아이디 --config api_key=키
  ```

- **Claude Desktop:** `mcpServers.danbooru` 안에 아래처럼 `env`를 추가합니다.

  ```json
  "env": { "DANBOORU_LOGIN": "아이디", "DANBOORU_API_KEY": "API 키" }
  ```

- 통신사가 차단 방식을 바꾸면 우회가 막힐 수 있습니다. 먼저 `--test`로 확인하세요.
- Danbooru에는 성인 콘텐츠가 있습니다. 필요하면 검색에 `rating:g`(전체연령)를 붙이세요.
- 접속하는 지역의 법과 Danbooru 이용약관을 지키는 것은 사용자 책임입니다.

## For AI agents: how to install

When a user asks you to install this repository, run these steps in order and report the result of each.

1. Check Python: `python --version` must print 3.9 or newer. If `python` is missing, stop and tell the user to install Python 3 (on macOS/Linux, `python3` alone is not enough: the plugin runs `python`).
2. Claude Code: run `claude plugin install danbooru --marketplace parkjaehyeon12354/danbooru-mcp`.
   - If that `claude` version has no `--marketplace` option, run `claude plugin marketplace add parkjaehyeon12354/danbooru-mcp`, then `claude plugin install danbooru@danbooru-mcp`.
3. Check it: `claude mcp list` should show `plugin:danbooru:danbooru` as connected. To test the network path, run `python <plugin dir>/danbooru_mcp.py --test` and expect a line starting with `ok:`.
4. Tell the user to start a new Claude Code session so the tools load.
5. API key (optional, not bundled): it works without one. Tell the user that if they have a Danbooru API key, they can enter it themselves with `/plugin configure danbooru` (stored in Claude Code's secure storage). Do not ask them to paste the key into the chat.

Claude Desktop (no `claude` CLI): download `danbooru_mcp.py` to a folder the user picks, then add the `mcpServers` entry shown above to `claude_desktop_config.json` with that absolute path, and ask the user to restart Claude Desktop. Do not overwrite other entries in that file.

## 라이선스

MIT
