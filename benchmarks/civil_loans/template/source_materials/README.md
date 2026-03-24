# Source Materials

Place the raw input documents for this benchmark case here before annotation.

## Required Documents for 民间借贷

| File (suggested name)        | Content                              | Required |
|------------------------------|--------------------------------------|----------|
| `loan_agreement.pdf`         | 借款合同或借条原件                   | 必须     |
| `transfer_records.pdf`       | 转账凭证（银行流水、支付截图等）     | 必须     |
| `repayment_records.pdf`      | 已还款记录（如有）                   | 如有     |
| `communication_records.pdf`  | 催款记录（短信、微信截图等）         | 如有     |
| `complaint.pdf`              | 起诉状                               | 必须     |
| `defense_statement.pdf`      | 答辩状（如有）                       | 如有     |

## Notes

- Do not include files containing personal identifiers outside the case team.
- Each document must be referenced by at least one `Evidence` object in `gold_evidence_index.json`.
- Filenames become the `source` field value in the corresponding Evidence object.
