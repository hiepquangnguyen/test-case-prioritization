from hcfalcon.lrts.java_parse import parse_java, select_methods, text_id

FOO = """package a.b;
import org.junit.Test;
public class FooTest extends Base {
  @Test(timeout=60000)
  public void testOne() throws Exception { int x = 1; // c
    assertEquals(1, x); }
  @org.junit.Test public void two() { new Thread() { public void run() {} }.start(); }
  public void testLegacy() {}
  public void testWithArg(int a) {}
  private void helper() {}
  @Before public void setUp() {}
  static class Inner { @Test void innerTest() {} }
}
"""


def test_finds_test_methods_and_drops_annotations():
    p = parse_java(FOO)
    assert p.package == "a.b" and not p.has_error
    by = {m.name: m for m in p.methods}
    assert set(by) == {"testOne", "two", "testLegacy", "testWithArg", "helper", "setUp", "innerTest"}  # not run()
    assert {n for n, m in by.items() if m.is_test} == {"testOne", "two", "testLegacy", "innerTest"}
    assert by["innerTest"].owner == "FooTest.Inner"
    assert by["testOne"].text.startswith("public void testOne() throws Exception {")
    assert "@Test" not in by["testOne"].text and "\n" not in by["testOne"].text
    kind, texts = select_methods(p, FOO)
    assert kind == "test" and len(texts) == 4


def test_fallbacks():
    base = "public abstract class BaseTest { protected void check() {} void helper() {} }"
    kind, texts = select_methods(parse_java(base), base)
    assert kind == "all" and len(texts) == 2
    junk = "this is not java at all"
    kind, texts = select_methods(parse_java(junk), junk.encode())
    assert kind == "file" and texts == [junk]


def test_text_id():
    assert text_id("void a() {}") == text_id("void a() {}") != text_id("void b() {}")
    assert len(text_id("x")) == 20
