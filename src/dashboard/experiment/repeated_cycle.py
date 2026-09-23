"""config/experiment.toml 조건으로 반복 왕복 실험을 실행합니다."""

if __package__:
    from .acquisition import main
else:
    from acquisition import main


if __name__ == "__main__":
    raise SystemExit(main())
