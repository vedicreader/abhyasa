# Walk trial

Guides: steps 5 to 12; passage on 70% of steps (a paper or docs walk); every question passes; grade right both ways; naive code fails and good code passes; no code check and right links on a tool walk; at most 30 s a step.

| walk | steps | with passage | figures | checks short/demo/order/code | one ask | grade round trip | code naive/good | Leela steps and links right | s/step | s/call | build s |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| attention | 12 | 9 (75%) | 3 | 8/0/2/2 | 8 of 8 | right both ways | 0 of 4 / 4 of 4 | - | 10.0 | 8.5 | 78 |
| pydantic-ai | 12 | 11 (91%) | 0 | 10/0/2/0 | 10 of 10 | right both ways | - | 10, 10 links, 10 pages | 16.1 | 11.1 | 132 |
| claude-code | 12 | 11 (91%) | 0 | 10/0/2/0 | 10 of 10 | right both ways | - | 2, 2 links, 2 pages | 13.2 | 8.0 | 114 |
| gradient-descent | 8 | 0 (0%) | 0 | 6/1/0/1 | 6 of 6 | right both ways | - | - | 12.9 | 9.3 | 25 |

## attention

- Inside every guide.
- Steps: 12, and 21 more ideas that are not steps; build 78 s; 33 model calls, 8.5 s each on average.
- Grade: the model answer graded correct: True; "I am not sure." graded not correct: True.
- Code: naive 0 of 4, good 4 of 4, 16 s.
- Screen: `attention-0.png`
- Screen: `attention-6.png`
- Screen: `attention-11.png`

## pydantic-ai

- Inside every guide.
- Steps: 12, and 52 more ideas that are not steps; build 132 s; 51 model calls, 11.1 s each on average.
- Grade: the model answer graded correct: True; "I am not sure." graded not correct: True.
- Leela: 10 steps with a link, 10 links right, 10 pages right, 0 code checks. 0 demo or order cards were not fetched (a demo card starts a demo job).
- Screen: `pydantic-ai-0.png`
- Screen: `pydantic-ai-6.png`
- Screen: `pydantic-ai-11.png`

## claude-code

- Inside every guide.
- Steps: 12, and 51 more ideas that are not steps; build 114 s; 41 model calls, 8.0 s each on average.
- Grade: the model answer graded correct: True; "I am not sure." graded not correct: True.
- Leela: 2 steps with a link, 2 links right, 2 pages right, 0 code checks. 1 demo or order cards were not fetched (a demo card starts a demo job).
- Screen: `claude-code-0.png`
- Screen: `claude-code-6.png`
- Screen: `claude-code-11.png`

## gradient-descent

- Inside every guide.
- Steps: 8, and 0 more ideas that are not steps; build 25 s; 25 model calls, 9.3 s each on average.
- Grade: the model answer graded correct: True; "I am not sure." graded not correct: True.
- Screen: `gradient-descent-0.png`
- Screen: `gradient-descent-4.png`
- Screen: `gradient-descent-7.png`
