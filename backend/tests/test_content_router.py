from app.routers.content import _extract_json


def test_extract_plain_json():
    s = '{"caption":"hi","hashtags":["a","b"],"voiceover_script":"vo"}'
    obj = _extract_json(s)
    assert obj["caption"] == "hi"
    assert obj["hashtags"] == ["a", "b"]


def test_extract_fenced_json():
    s = """```json
{
  "caption": "hello",
  "hashtags": ["x"],
  "voiceover_script": "test"
}
```"""
    obj = _extract_json(s)
    assert obj["caption"] == "hello"


def test_extract_with_prose():
    s = """Sure, here is the JSON you wanted:
{
  "caption": "yo",
  "hashtags": ["one"],
  "voiceover_script": "go"
}
Hope this helps!"""
    obj = _extract_json(s)
    assert obj["caption"] == "yo"
