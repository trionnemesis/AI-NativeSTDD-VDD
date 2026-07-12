# 21 · Evidence、Provenance 與 Audit Contract

> **Authority boundary**：此頁是 [Notion 21｜Evidence、Provenance 與 Audit Contract](https://app.notion.com/p/399f5b2d1a90819eb4e1fb0033a3d652) 的 repository human reference。可用 example 見 [`governance/examples/evidence-envelope.yaml`](../governance/examples/evidence-envelope.yaml)；Notion 摘要與 agent 自述都不是完整 machine artifact。

## Evidence states

每個 assertion 的 evidence 只能處於明確狀態：

| State | Meaning |
|---|---|
| `verified` | 可定位、完整、可重跑且在 policy freshness 內的 artifact 支持結論。 |
| `assumed` | 尚未驗證的假設；不得當作 pass。 |
| `missing` | 必要 artifact 不存在或不可取得；gate 應 fail/defer。 |
| `stale` | context、policy、subject 或有效期已改變，需重新取證。 |
| `not_applicable` | 由 profile policy 解析、有 reason code、alternative evidence 與核准路徑；不是自由文字 skip。 |

## Evidence Envelope

每個可採用 evidence 應綁定以下欄位：

```text
subject, change, gate, policy version, actor, tool/model, environment,
input/output hashes, oracle, artifact URI/hash, signature, retention,
freshness, trust label, and provenance links
```

Evidence 必須可歸因、具 integrity protection、可重現、scope 正確、仍新鮮且 privacy-safe。對 runtime evidence 而言，machine artifact 是 authority；Notion 仍是方法論的 canonical source，不能以 human-readable summary 取代可驗證 proof。

## Provenance chain

```text
SIG:* → ADMIT:* → tier / dispatch / worktree attestation
      → Change Intent / Delta Spec / profile resolution
      → requirement / test / Red-or-alternative evidence
      → quality / release / production observation
      → EVID:* envelope index
```

每個 Gate pass/fail、N/A、waiver 和 human decision 都應可回溯到這個 chain。Relevant change、policy update、artifact replacement 或 retention expiry 會使前一份 evidence stale；刪除 artifact 時保留 tombstone 與原因，不能抹除 audit history。

## Retention and review

- policy 定義 retention、freshness、signature/checksum、access control 和 review owner。
- privacy/security evidence 必須避免在 prompt、log、PR 或 memory 暴露 restricted data/secrets。
- replay 時固定或記錄 model、prompt、tool policy、routing、environment、seed 和 budget，避免不可解釋的差異。
- evidence 缺失或不一致時 loud fail；不能以截圖、自然語言完成宣告或單一 LLM judge 補洞。

相關頁面：[07｜Canonical Pipeline](07-canonical-pipeline.md)、[20｜Agent Security](20-agent-security-privacy-threat-model.md)、[23｜Agent EvalOps](23-agent-evalops-configuration-regression.md)。
