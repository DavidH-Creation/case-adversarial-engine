# 浜夌偣鎶藉彇鍣ㄥ悎鍚?(Issue Extractor Contract)

## 姒傝堪
浜夌偣鎶藉彇鍣ㄨ礋璐ｄ粠宸茬粨鏋勫寲鐨?Claim銆丏efense銆丒vidence 涓彁鍙栦簤璁劍鐐癸紙Issue锛夛紝鏋勫缓浜夌偣鏍戯紝骞朵负姣忎釜鏍稿績浜夌偣鍒嗛厤涓捐瘉璐ｄ换锛圔urden锛夈€?

## 杈撳叆
| 瀛楁 | 绫诲瀷 | 璇存槑 |
|------|------|------|
| claims | Claim[] | 鍘熷憡涓诲紶鍒楄〃锛岄』绗﹀悎 claim.schema.json |
| defenses | Defense[] | 琚憡鎶楄京鍒楄〃锛岄』绗﹀悎 defense.schema.json |
| evidence | Evidence[] | 宸茬储寮曡瘉鎹垪琛紝椤荤鍚?evidence.schema.json |

## 杈撳嚭
浜х墿涓?IssueTree 瀵硅薄锛岄』绗﹀悎 `issue_tree.schema.json`锛屽寘鍚細
- **issues**: Issue 瀵硅薄鏁扮粍锛屾瘡涓?Issue 缁戝畾 `related_claim_ids`, `related_defense_ids`, `evidence_ids`, `burden_ids`
- **burdens**: Burden 瀵硅薄鏁扮粍锛屾瘡涓牳蹇?Issue 鑷冲皯涓€涓?Burden
- **claim_issue_mapping**: 姣忎釜 Claim 鍒?Issue 鐨勬槧灏?
- **defense_issue_mapping**: 姣忎釜 Defense 鍒?Issue 鐨勬槧灏?

## 绾︽潫瑙勫垯
1. **瀹屾暣鏄犲皠**锛氭瘡涓?Claim 鑷冲皯鏄犲皠涓€涓?Issue锛涙瘡涓?Defense 鑷冲皯鏄犲皠涓€涓?Issue
2. **灞傜骇缁撴瀯**锛欼ssue 浣跨敤 `parent_issue_id` 琛ㄧず灞傜骇鍏崇郴锛堝钩閾哄垪琛紝闈炲祵濂?JSON锛?
3. **涓捐瘉璐ｄ换**锛氭瘡涓牳蹇?Issue锛堟棤 parent 鎴栦负椤跺眰浜夌偣锛夎嚦灏戝垎閰嶄竴涓?Burden
4. **浜嬪疄鍛介**锛歚fact_propositions` 浣跨敤缁撴瀯鍖栧璞?`{proposition_id, text, status, linked_evidence_ids}`
5. **寮曠敤瀹屾暣鎬?*锛氭墍鏈?`evidence_ids` 蹇呴』鎸囧悜杈撳叆涓瓨鍦ㄧ殑 Evidence锛涙墍鏈?`burden_ids` 蹇呴』鎸囧悜杈撳嚭涓殑 Burden
6. **闄堣堪鍒嗙被**锛氭瘡涓浉鍏崇殑 AgentOutput 蹇呴』鏍囨敞 `statement_class`锛坒act/inference/assumption锛?

## 涓嶅惈
- 娉曞畼 agent 閫昏緫
- 澶氳疆瀵规姉妯℃嫙
- 妗堢鐗瑰畾鐭ヨ瘑纭紪鐮侊紙姘戦棿鍊熻捶鍏稿瀷浜夌偣浠呭湪 fixture 涓綋鐜帮級

## 杩愯鏂瑰紡
- 閫氳繃 Job + Run 绠＄悊
- Job.result_ref 鎸囧悜浜у嚭鐨?IssueTree

## 楠屾敹鏍囧噯
- `issue_extraction_accuracy >= 80%`锛堜笌閲戞爣浜夌偣鏍戞瘮瀵癸級
- `citation_completeness = 100%`锛堝叧閿粨璁哄繀椤绘湁 evidence_id 寮曠敤锛?
- 闆?`parent_issue_id` 鎮┖寮曠敤
- 闆?Claim/Defense 鏈槧灏?
