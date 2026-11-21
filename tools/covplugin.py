import os, sys, json, coverage, pytest
ROOT = os.environ.get("COV_ROOT", "/work/sqlglot") + "/"
_cov = None
_cur = [None]
_opens = {}
_mods = {}
_cls = {}
_ecls = {}
_eager = []
COVDIR = os.environ.get("COV_DIR", "/work/covdata")
WID = os.environ.get("PYTEST_XDIST_WORKER", "main")


def _audit(ev, args):
    if ev == "open" and _cur[0] is not None:
        p = args[0]
        if isinstance(p, str) and p.startswith(ROOT) and not p.endswith(".pyc"):
            _opens.setdefault(_cur[0], set()).add(p[len(ROOT):])


def _wrap(cls):
    orig = cls.__init__

    def init(self, *a, **k):
        if _cur[0] is not None:
            s = _cls.setdefault(_cur[0], set())
            for c in type(self).__mro__:
                m = c.__module__
                if m.startswith("sqlglot"):
                    s.add(m)
        return orig(self, *a, **k)

    cls.__init__ = init


class _InlineExecutor:
    def __init__(self, max_workers=None, mp_context=None, initializer=None, initargs=(), **kw):
        if initializer:
            import pickle
            a = pickle.loads(pickle.dumps(initargs))
            initializer(*a)

    def submit(self, fn, *a, **k):
        from concurrent.futures import Future
        import pickle
        f = Future()
        try:
            fn, a, k = pickle.loads(pickle.dumps((fn, a, k)))
            f.set_result(pickle.loads(pickle.dumps(fn(*a, **k))))
        except BaseException as e:
            f.set_exception(e)
        return f

    def map(self, fn, *its, **kw):
        return [fn(*a) for a in zip(*its)]

    def shutdown(self, *a, **k):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def _wrap_expr(cls):
    orig = cls.__init__

    def init(self, *a, **k):
        if _cur[0] is not None:
            s = _ecls.setdefault(_cur[0], set())
            for c in type(self).__mro__:
                m = c.__module__
                if m.startswith("sqlglot.expressions"):
                    s.add(m + ":" + c.__name__)
        return orig(self, *a, **k)

    cls.__init__ = init


def pytest_configure(config):
    import concurrent.futures as cf
    cf.ProcessPoolExecutor = _InlineExecutor
    global _cov
    _cov = coverage.Coverage(data_file=f"{COVDIR}/.cov.{WID}", source=[ROOT + "sqlglot"], data_suffix=False)
    _cov.start()
    sys.addaudithook(_audit)


def pytest_collection_finish(session):
    from sqlglot import parser, generator, tokens
    from sqlglot.dialects import dialect
    for c in (parser.Parser, generator.Generator, tokens.Tokenizer, dialect.Dialect):
        _wrap(c)
    from sqlglot import exp
    _wrap_expr(exp.Expr)
    _eager.extend(m for m in sys.modules if m.startswith("sqlglot"))


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_protocol(item, nextitem):
    _cov.switch_context(item.nodeid)
    _cur[0] = item.nodeid
    before = set(m for m in sys.modules if m.startswith("sqlglot"))
    yield
    after = set(m for m in sys.modules if m.startswith("sqlglot"))
    _mods[item.nodeid] = after - before
    _cur[0] = None


def pytest_unconfigure(config):
    _cov.stop()
    _cov.save()
    out = {"opens": {k: sorted(v) for k, v in _opens.items()},
           "mods": {k: sorted(v) for k, v in _mods.items() if v},
           "cls": {k: sorted(v) for k, v in _cls.items()},
           "ecls": {k: sorted(v) for k, v in _ecls.items()},
           "eager": sorted(set(_eager))}
    json.dump(out, open(f"{COVDIR}/extra.{WID}.json", "w"))
