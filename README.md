# Garden

Garden은 에이전트 공통 지침과 전역 설정을 관리하는 저장소다.
신규 프로젝트의 목적, 범위와 이름을 논의하고 요청받은 저장소를 생성하는 기준도 관리한다.

현재 자동 연결 대상은 Codex 전역 지침과 Garden 할 일 경로다.
Claude와 다른 전역 설정의 적용 상태는 [전역 설정 관리 기준](docs/global-settings.md)에서 관리한다.
공통 Git 훅의 설치와 갱신은 [Hortulanus](https://github.com/Olbbemi/Hortulanus)가 담당한다.

## 관리 문서

| 문서 | 내용 |
| --- | --- |
| [Garden 작업 지침](AGENTS.md) | Garden의 책임과 작업별 문서 확인 기준 |
| [전역 공통 지침](global/AGENTS.md) | 모든 프로젝트의 대화, 작업 범위와 할 일 관리 규칙 |
| [전역 설정 관리 기준](docs/global-settings.md) | 관리 대상, 적용 상태와 검증 기준 |
| [프로젝트 명명과 생성 기준](docs/project-creation.md) | 이름 선정과 저장소 생성 절차 |
| [프로젝트 기록](docs/projects.md) | 프로젝트별 역할, 이름 선정 근거와 생성 결과 |
| [할 일과 변경 요청](data/todo/README.md) | Garden의 보류 작업과 다른 프로젝트에서 전달한 요청 |
| [작업 목록](TODO.md) | 기존 작업의 진행 현황과 구현 결과 |

참고 문서는 `docs/`에, 할 일과 요청은 `data/todo/`에 둔다.
공용 접근 경로는 `~/.local/share/garden/todo/`다.

## Codex 전역 지침 배치

Codex 전역 지침에는 `global/AGENTS.md`를 연결한다.
루트 `AGENTS.md`는 Garden 전용 지침이다.

```text
~/.codex/AGENTS.md -> <Garden 경로>/global/AGENTS.md
~/.local/share/garden -> <Garden 경로>/data
```

`CODEX_HOME`을 지정했다면 해당 디렉터리의 `AGENTS.md`에 연결한다.
값은 비어 있지 않은 절대 경로여야 한다.

### 자동 연결

Hortulanus의 공통 Git 훅을 사전 설치한 환경에서는 Garden을 clone할 때 자동 연결한다.
Garden의 `tools/scripts/git/post-checkout`이 두 링크 스크립트를 호출하며,
`data/todo/`가 없으면 함께 만든다.
프로젝트 훅과 스크립트가 clone한 체크아웃에 포함되어 있어야 한다.

- `origin`이 GitHub의 `Olbbemi/Garden`인 저장소만 대상으로 한다.
  HTTPS와 SSH 주소를 지원하며 끝의 `.git`은 생략할 수 있다.
- 최초 checkout에서만 실행한다.
  일반 checkout/switch와 추가 worktree 생성에서는 연결을 변경하지 않는다.
- `--no-checkout`, bare clone, 별도 `--template`이나 훅 실행 경로를 사용한 경우에는
  자동 연결을 기대하지 않는다.
  일반 작업 트리의 Garden 루트에서 수동 연결한다.

### 기존 체크아웃의 연결

공통 훅이 없는 기존 Garden에는 Hortulanus의 설치 및 갱신 절차를 먼저 적용한다.
아래는 두 저장소가 같은 상위 디렉터리에 있고 Hortulanus가 이미 설치된 경우의 명령이다.
Garden 루트에서 실행하며, 배치가 다르면 설치기 경로를 바꾼다.
공통 훅이 이미 연결되어 있다면 이 단계는 생략한다.

```bash
python3 -I -B ../Hortulanus/scripts/install.py update --repo . --dry-run
python3 -I -B ../Hortulanus/scripts/install.py update --repo .
```

지침과 할 일 경로는 Garden 루트에서 다음 명령으로 연결한다.
자료 경로의 충돌을 먼저 확인하며, `--dry-run`은 변경하지 않는다.

```bash
python3 -B scripts/link_shared_todo.py . --dry-run
python3 -B scripts/link_codex_agents.py .
python3 -B scripts/link_shared_todo.py .
```

연결 결과는 다음 명령으로 확인한다.
별도 `CODEX_HOME`을 사용하면 첫 번째 경로를 해당 디렉터리의 `AGENTS.md`로 바꾼다.

```bash
readlink -f ~/.codex/AGENTS.md
readlink -f ~/.local/share/garden
```

### 충돌 처리

같은 원본을 가리키는 링크는 유지한다.
일반 파일, 디렉터리, 다른 대상의 링크와 끊어진 링크는 보존하고 오류로 알린다.
두 번째 clone이나 구 배치 구조도 자동으로 전환하지 않는다.
기존 대상과 자료를 확인하고 필요한 백업 및 정리를 마친 뒤 스크립트를 다시 실행한다.

clone이 링크 충돌로 실패해도 다운로드와 checkout은 끝났을 수 있다.
두 링크 생성은 원자적 작업이 아니므로 실패 후에는 실제 연결 상태를 확인한다.
자동 연결은 자료 경로의 기존 충돌을 지침 링크 생성 전에 확인한다.

지침 링크 스크립트는 비어 있지 않은 `AGENTS.override.md`가 있으면 안내를 출력하고 파일을 유지한다.
Git 설정과 공통 훅 설치의 충돌은 Hortulanus의 안내를 따른다.

### 업데이트와 해제

Garden의 프로젝트 훅과 링크 스크립트만 변경했다면 공통 훅을 재설치할 필요가 없다.
공통 연결 코드의 갱신과 제거는 Hortulanus에서 진행한다.

Garden 연결을 해제할 때는 실제 대상이 Garden인지 확인한 뒤 해당 심볼릭 링크만 제거한다.
`global/AGENTS.md`와 `data/`의 원본은 유지한다.

## 검증

Garden의 프로젝트 훅과 두 링크 스크립트는 다음 명령으로 검증한다.

```bash
python3 -B -m unittest discover -s tests -v
```

테스트는 임시 HOME과 Git 설정, 로컬 저장소를 사용한다.
네트워크에 접속하거나 실제 사용자 설정을 변경하지 않으며 Hortulanus 체크아웃은 필요 없다.
검증 대상은 링크 생성, 충돌 보존과 실행 조건이다.
