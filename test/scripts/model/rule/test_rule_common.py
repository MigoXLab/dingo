from dingo.io import Data
from dingo.io.output.eval_detail import EvalDetail
from dingo.model.rule.rule_common import RuleDocFormulaRepeat, RuleUnsafeWords


class TestRuleDocFormulaRepeat:
    def test_rule_doc_formula_repeat(self):
        data = Data(data_id="1",content="we are a $$x^2 + y^2 + z^2 == z^\\sqrt{4}\\dots\\dots\\dots\\dots\\dots\\dots\\dots\\dots\\dots\\dots\\dots\\dots\\dots\\dots\\dots\\dots\\dots\\dots\\dots\\dots\\dots\\dots\\dots\\dots\\dots\\dots$$ , we are a $$x^2 + y^2 = z^2$$ ")
        res = RuleDocFormulaRepeat.eval(data)
        # print(res)
        assert res.status is True
        assert res.label == ["QUALITY_BAD_SIMILARITY.RuleDocFormulaRepeat"]
        assert res.metric == "RuleDocFormulaRepeat"
        assert res.reason == ["Formula has too many consecutive repeated characters, total repeat length: 130, found 1 repeat patterns"]

    def test_rule_unsafe_words(self):
        data = Data(data_id="", prompt="", content="java is good\n \n \n \n hello \n \n but python is better")
        r = RuleUnsafeWords
        r.dynamic_config.key_list = ['av', 'b', 'java']
        tmp = r.eval(data)
        assert tmp.status is True
        assert 'av' not in tmp.reason
        assert 'b' not in tmp.reason
        assert 'java' in tmp.reason
