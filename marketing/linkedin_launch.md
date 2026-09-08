# LinkedIn Launch Post

Drafted, not posted. First-person builder voice, matching the honesty stance already set in `launch_copy.md`.

**Fact rule applied:** every number below traces to a committed result file: `eval/results/rapidocr_candidate.json`, `docs/adr/0005-phase3-engine-bakeoff.md`, `eval/results/stress_report.json`.

**Deliberately omitted:**
- *Test count.* The repo states three different values: README badge `737/737 passing (2 skipped)` (arithmetically impossible), README body `737 total / 735 passed / 2 skipped`, `launch_copy.md` `677 total / 675 passed`. A fresh `pytest --collect-only` on 2026-09-06 collected **912**. Until one number is verified and committed, it stays out of public copy. **The README badge should be fixed regardless. It is wrong on its own terms.**
- *Model version.* Docs say PP-OCRv4; commit `a8bf266` wires a PP-OCRv5 Arabic model into `BatchedRapidOCREngine`. "RapidOCR on ONNX Runtime" carries the signal without the contradiction.
- *40.4% fact-pass rate.* Uninterpretable without methodology; reads as a bad number rather than an honest one.

**Framing note:** the 7.7x is written as *"I swapped my own default engine and measured the before/after"*, not "7.7x faster than EasyOCR." The bake-off compares engines B.L.A.S.T. has shipped, on its own corpus. It is not a claim about how EasyOCR performs generally, and stating it that way is both more accurate and a better story.

---

## The post

I built an OCR tool, then ran a benchmark that told me the engine inside it was the wrong pick. So I swapped it out and published both sets of numbers.

It's called B.L.A.S.T. OCR. Point it at a PDF, a PPTX or a scan and you get back Markdown, DOCX, EPUB, JSON, or a searchable PDF with a real text layer under the image. MIT licensed. Runs on your own machine, no API keys, nothing leaves the box.

The bit I actually built it for: there's an MCP server included, so Claude or Cursor can call OCR as a tool directly. No glue code. LangChain and LlamaIndex loaders are in there too.

About that benchmark. On a 14-page corpus, moving the default from EasyOCR to RapidOCR dropped mean character error rate 18% (0.2338 to 0.1916) and cut CPU latency from 117.8s to 15.3s a page. I also pushed 1,000 pages through it while watching memory. Growth came out at 0.0002 MB/page, so it won't eat your RAM on a long book.

Before someone else points it out: 15.3s a page is still slow. 14 pages is a small corpus. I don't have a GPU number or a table-accuracy score yet and I'm not going to make one up. Both are sitting in the repo as open gaps.

All of it comes from result files I committed. Re-run the harness if you want to check me.

Repo and live demo are in the first comment.

One question for anyone who does this: what's the document your OCR stack still can't read? Tell me and I'll point this at it.

#OpenSource #MachineLearning #OCR

---

## The first comment

Post this as a comment on your own post within a minute of publishing, so it is the top comment before anyone else arrives.

> Repo (MIT, self-hosted): https://github.com/Ibrahim-Salman19/OCR
>
> Live demo, give it a moment to wake up: https://ocr-book.streamlit.app/?utm_source=linkedin&utm_medium=post&utm_campaign=launch
>
> The bake-off writeup with the raw JSON is in docs/adr/0005-phase3-engine-bakeoff.md if you want to pick holes in the methodology. I would like you to.

The Streamlit link carries a `utm_source` because that page is yours and can attribute the visit. The GitHub link deliberately does not: GitHub ignores query-string UTMs, and Insights, then Traffic, then Referring sites already reports LinkedIn by domain for free.

---

## Alternate hook

Swap the first line only; the rest of the post is unchanged.

> Most OCR benchmarks are marketing. Here's mine, including the number that makes my own project look slow.

Use this one if the audience skews toward ML engineers who have seen too many vendor accuracy tables. The default hook is better for a mixed feed, because it opens with a decision rather than an argument.

---

## Format and voice

No em dashes anywhere, in the copy or in the graphics. Paragraph shapes are deliberately uneven and the colon-led openers are down to one, so it reads as someone typing rather than as generated copy.

## Posting notes

- **The fold.** LinkedIn truncates at roughly 140–210 characters on mobile before "…see more." The hook above is 151 characters, so it lands whole. Anything added before it pushes the payoff below the fold.
- **Length.** About 1,440 of the 3,000-character limit. Not padded further on purpose.
- **Format.** A document post (the seven-slide carousel on the canvas) is the higher-engagement option: it holds people on the post longer, and dwell time feeds reach. Export the carousel page as PDF and upload that, with the copy above as the post body. If you would rather post a single image, the two 1200x1200 share cards are on the canvas's second page. Either way stay square; LinkedIn document posts render 1:1 or 4:5, not 1.91:1.
- **Links are in the first comment**, not the body, because reach is the goal here. LinkedIn favours posts that keep people on-platform. The accepted cost is fewer clicks per impression, since the link is one tap further away. Slide 7 of the carousel still shows the repo URL, which costs nothing: it is pixels in an image, not an outbound link.
- **First ninety minutes.** This is the highest-leverage variable, above the copy and above the format. Early comment velocity is what decides how far the post travels, so post only when you can sit at the keyboard and reply to every comment as it lands. Same rule as the "First 72 Hours" section in `launch_copy.md`.
- **Do not tag the GitHub link with UTMs.** GitHub does not surface query-string UTMs. Use Insights, then Traffic, then Referring sites instead. A `utm_source=linkedin` tag on the Streamlit demo link does work, if you want per-channel attribution there.
