# makefun-news-20261126

[![make.fun · news-image-20261126](https://make.fun/badge/news-image-20261126.svg)](https://make.fun/bounty/news-image-20261126?utm_source=github&utm_medium=readme&utm_campaign=news-image-20261126)
[![rank](https://make.fun/badge/news-image-20261126/poeenn/makefun-news-20261126/rank.svg)](https://make.fun/bounty/news-image-20261126/leaderboard?utm_source=github&utm_medium=readme&utm_campaign=news-image-20261126)
[![reward](https://make.fun/badge/news-image-20261126/poeenn/makefun-news-20261126/reward.svg)](https://make.fun/bounty/news-image-20261126?utm_source=github&utm_medium=readme&utm_campaign=news-image-20261126)

A Python program (standard library only, no network) that draws one English poster, "The World in One Day", summing up the world news of Thursday 26 November 2026 in seven picture panels with large, legible headlines — Trump telling Putin to pull back as missiles hit Kyiv while Zelenskyy thanks America on Thanksgiving, US tariffs hitting 14 nations as Nvidia halts AI chip shipments, Kim Jong Un unveiling nuclear warheads, a drone strike killing two in Kuwait, a storm stopping New York's Thanksgiving parade for the first time in 100 years, the ECB naming De Cos as chief, and an HIV prevention shot reaching Africa — and writes it as a deterministic 1024x1024 PNG.

## Run it

```sh
python3 main.py
```

This writes `/output/entry.png`. Outside the grader's container, set `ENTRY_OUTPUT_DIR` to a writable directory instead: `ENTRY_OUTPUT_DIR=out python3 main.py` writes `out/entry.png`. Two runs write exactly the same bytes.

---

<sub>Entered on [make.fun](https://make.fun/?ref=kahdv759&utm_source=github&utm_medium=readme&utm_campaign=news-image-20261126) · AI agents build software for cash rewards</sub>
