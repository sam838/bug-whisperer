# Evidence 003: works on a website we didn't build

**Status: 🐛 reproduced by Kane CLI and double-checked** (Nov 13, 2026). This is a **link-only**
app: Bug Whisperer has no access to its code, so it reports the bug and doesn't fix it.

**The app:** [LambdaTest eCommerce Playground](https://ecommerce-playground.lambdatest.io), a public
demo shop LambdaTest made for practising test automation. It was connected through Bug
Whisperer's **Apps** page with nothing but its link and one line of description
([lambdatest-ecommerce-playground.json](lambdatest-ecommerce-playground.json)).

## The report, as written

> your search is broken. i typed canon camera and it says no products?? you literally sell canon
> cameras, i saw them yesterday. lost a sale because of this

## What happened

| Step | Kane CLI | Result |
|---|---|---|
| Reproduce: search "canon camera" ([reproduce-1.ndjson](reproduce-1.ndjson)) | ❌ failed | "There is no product that matches the search criteria." ([kane-saw.jpg](kane-saw.jpg)) |
| Double-check the user's claim: search "canon" ([claim-check.ndjson](claim-check.ndjson)) | ✅ passed | A Canon product is listed, so the shop does sell Canon cameras |
| Verdict | | 🐛 **Reproduced:** the search finds "canon" but not "canon camera". It fails as soon as the words aren't all in the product name |

## Why the double-check exists: an honest note

The first run of this same report ([first-run-before-double-check.json](first-run-before-double-check.json))
also said "reproduced", but for a bad reason. Kane showed only that "canon camera" finds nothing.
The judge (Claude) then assumed, **from its own memory**, that the shop sells a "Canon EOS 5D".
Kane's own label said the opposite (*"Search expectation assumes an unavailable Canon camera
match"*). The judge happened to be right, but a verdict built on memory isn't proof.

So we added the **claim double-check**. When a verdict relies on something the user claimed that
Kane didn't show, Claude writes one short extra Kane check for it. Kane passing confirms the bug.
Kane failing means the user's premise is wrong, and the verdict becomes "not reproduced". This
run used it, and the verdict now rests only on what Kane saw.

Cost: about 41 Kane credits (23 for the reproduction, 18 for the double-check), and about 1.5 minutes.
