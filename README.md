# claude-skill-nano-banana

Claude Code 스킬 — Google **Nano Banana** (Gemini 이미지 모델, Vertex AI) 로
이미지를 **생성·편집**합니다. 텍스트→이미지, 기존 이미지 편집(`--ref`), 다중 참조 합성까지.

> 디자이너·비개발자용 안내입니다. **터미널 명령을 직접 칠 필요 없습니다** —
> Claude Code 채팅창에 한국어로 부탁하면 Claude 가 알아서 처리합니다.

---

## 설치 (한 번만)

이미 nano-banana 를 zip 등으로 받아 쓰던 분도, 아래로 git 버전으로 교체하면
앞으로 갱신이 훨씬 쉬워집니다.

### Claude Code 에게 이렇게 부탁하세요 (권장)

> "이 repo 에서 nano-banana 스킬을 `~/.claude/skills/nano-banana` 에 설치해줘.
> 기존 폴더가 있으면 지우고 새로 clone 해줘:
> `https://github.com/hwangx/claude-skill-nano-banana`"

Claude 가 기존 폴더 제거 → `git clone` 까지 해줍니다. 끝나면 **Claude Code 를 재시작**하세요.

### (참고) 수동 설치 명령

```bash
rm -rf ~/.claude/skills/nano-banana
git clone https://github.com/hwangx/claude-skill-nano-banana ~/.claude/skills/nano-banana
```

> 이 repo 가 public 이면 인증 없이 바로 clone 됩니다. (private 포크라면 처음 한 번
> GitHub 로그인이 필요 — `gh auth login` 또는 로그인 팝업을 따르세요. 이 인증만은
> 본인 계정이라 Claude 가 대신 못 합니다.)

---

## 갱신 (스킬이 업데이트되면)

> "nano-banana 스킬 최신으로 업데이트해줘"

Claude 가 `git pull` 해줍니다. (수동: `cd ~/.claude/skills/nano-banana && git pull`)

---

## 사전 준비 (이미 `gemini-consult` 써봤으면 끝)

이 스킬은 사용자 **본인 GCP 프로젝트**의 Vertex AI 로 이미지를 만듭니다 (그쪽으로 과금):

- `pip install google-genai`
- `gcloud auth application-default login`
- 본인 GCP 프로젝트에 **Vertex AI API 활성화 + 결제 연결**

---

## 쓰는 법 — 채팅으로 부탁만

| 하고 싶은 것 | 이렇게 말하면 됨 |
|---|---|
| 이미지 생성 | "가을 아침 정원사 일러스트 만들어줘, 세로로" |
| 로고·OG 카드 (글자) | "지금알바 OG 카드 만들어줘" (Claude 가 텍스트 정확한 Pro 로 자동 격상) |
| 기존 이미지 편집 | "이 이미지 배경만 네이비로 바꿔줘" (`--ref` 자동 사용) |
| 시리즈 톤 통일 | 작업 폴더에 `DESIGN.md` 두고 "이 톤으로 만들어줘" |

자세한 사용법·프롬프트 요령은 디자이너용 가이드 문서를 참고하세요.

---

## 구성

```
nano-banana/
├── SKILL.md                     스킬 본체 (Claude 가 읽는 지침)
├── scripts/generate.py          Vertex AI 호출 (google-genai SDK, stdlib only)
└── references/
    ├── prompting-guide.md       5슬롯 프롬프트·텍스트 렌더링·카메라 제어·편집 패턴
    └── api-reference.md          모델·옵션·비용·에러 레퍼런스
```

세 모델: `nano-banana-2`(기본·빠름), `nano-banana-pro`(텍스트·고품질), `nano-banana`(legacy).
Claude 가 요청 내용 보고 자동 선택하며, "프로로" 처럼 직접 지정도 가능합니다.

---

*This project is independent and not affiliated with, endorsed by, or sponsored
by Anthropic or Google. "Claude", "Claude Code", "Gemini", and "Nano Banana" are
trademarks of their respective owners. Licensed under MIT — see [LICENSE](LICENSE).*
