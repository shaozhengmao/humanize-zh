# 开发验证工具

这些工具独立于 Skill，用于发现部分错误和复现工具行为。它们不能证明文章“像真人”或完全保真。

## 本地回归

Python 3.9+，无额外依赖、无需网络或 API key：

```bash
python3 -B tests/check_skill.py --selftest
python3 -B -m unittest discover -s tests -p 'test_*.py' -v
```

`check_skill.py` 检查元数据和本地引用，不要求固定章节或具体措辞。回归测试覆盖数量删改、单位变化、引语保留、默认不加载风格、重试失败、最终输出核对、配置错误和不覆盖既有文件等行为。

通过这些测试只说明被测工具行为符合预期，不能据此声称生成文章的质量得到提升。

## 词面辅助检查

```bash
python3 tests/claimcheck.py 原文.md 输出.md
python3 tests/fidelity.py 输出.md tests/fixtures/oss_article.json
```

- `claimcheck.py` 双向比较常见数量及单位、年份、书名；支持部分中文/阿拉伯数字和金额等价形式。引语变化提示人工复核。退出码 0=未发现所检查项目差异，1=有差异，2=输入错误。
- `fidelity.py` 检查配置中的 `must_contain` / `must_not_contain` 字符串，配置必须包含至少一条有效断言。退出码同上。它只能识别列出的情况，不能拦住所有编造。

两者均不理解事实关系。比如“不建议投资”改成“建议投资”、两个人的数值互换、删掉信源等仍可能不报错。数字相同不代表事实相同。合法摘要、推算结果或同义表达也可能触发差异；差异应人工复核，不能为了通过检查机械补回数字。复杂日期、范围、分数和不常见计量表达未做完整解析。

## 可选 API 改写

显式运行 `gate.py` 且设置 `DEEPSEEK_API_KEY` 时，输入文章及所选风格会发送至 DeepSeek。普通本地测试不发请求。

```bash
python3 tests/gate.py 原文.md --out 终稿.md
python3 tests/gate.py 原文.md --voice 自选风格.md --max-retries 3
python3 tests/gate.py 原文.md --key tests/fixtures/oss_article.json
```

默认沿用作者语气，不加载人物声音、不自动删词。每个候选稿对照原文核对数量等词面变化；可叠加固定断言。仅在发现差异时重试，达到次数上限仍有差异则退出 2，不输出候选稿。检查最终文本后不再做修改。

无 API key 时原样返回，并提示未执行改写；API 失败退出 1，不返回改坏的稿件。无效参数或配置退出 2。`--warn-only` 可以显式输出含待复核差异的稿件，不绕过输入错误或 API 错误。检查失败时不覆盖 `--out` 指向的既有文件。

引语被忠实转述也会产生提示，因此提示本身不阻止输出；直接引语的准确性、信源和立场仍须人工检查。所谓“通过”仅限已执行的词面检查。

## 历史特征与模型复核

```bash
python3 tests/score.py
python3 tests/score.py --rewrites tests/rewrites
python3 tests/score.py --rewrites tests/rewrites --judge
```

`linter.py` / `score.py` 保留历史词频与句长特征，便于查看旧实验；`tell_score` 曾出现样本排序反转，下降不代表改写成功，不能当阈值、质量评分或检测器。

`--rewrites` 按 manifest 的样本 id 寻找同名 Markdown 文件，只对找到的改写执行原文词面核对和可用的固定断言，不要求 API。现有 `oss_rewrite.md` 没有对应的 ai 样本 id，不在该路径内自动参与比较，可单独使用 `fidelity.py` 检查。

`--judge` 额外将找到的原文与改写发送至 DeepSeek，获取新增断言、立场偏移和语言问题建议。模型可能误判或漏判，主观分数不能提供事实保证。历史 corpus 的 human/ai 标签不是经独立核验的真实性证据。

## 判断 Skill 是否值得保留

用真实任务比较同一模型加载与不加载 Skill 的表现。固定素材、篇幅与写作要求，匿名混排结果，分别评价事实与限定是否保留、作者语气是否合适、表达是否清楚、需要多少返工。包括“原文已经自然”的情况，允许不改。

优先覆盖：非虚构缺资料、纯观点短文、明确的虚构创作、混合文体、直接引语、必要反方论述、信源和否定限定，以及用户主动选择风格。工具回归不能替代这些实际写作比较；现有语料规模和标签来源不足以证明普遍效果。
