import inspect
import sqlite3
import unittest
from io import StringIO

from littleutils import SimpleNamespace

from sorcery import spells
from sorcery.core import _resolve_var
from sorcery.spells import unpack_keys, unpack_attrs, print_args, magic_kwargs, maybe


class MyListWrapper(object):
    def __init__(self, lst):
        self.list = lst

    def _make_new_wrapper(self, method_name, *args, **kwargs):
        method = getattr(self.list, method_name)
        new_list = method(*args, **kwargs)
        return type(self)(new_list)

    append, extend, clear, __repr__, __str__, __eq__, __hash__, \
        __contains__, __len__, remove, insert, pop, index, count, \
        sort, __iter__, reverse, __iadd__ = spells.delegate_to_attr('list')

    copy, __add__, __radd__, __mul__, __rmul__ = spells.call_with_name(_make_new_wrapper)


class Foo(object):
    @magic_kwargs
    def bar(self, **kwargs):
        return set(kwargs.items()) | {self}


class TestStuff(unittest.TestCase):
    def test_unpack_keys_basic(self):
        obj = SimpleNamespace(thing=SimpleNamespace())
        d = dict(foo=1, bar=3, spam=7, x=9)
        foo, obj.thing.spam, obj.bar = unpack_keys(d)
        self.assertEqual(foo, d['foo'])
        self.assertEqual(obj.bar, d['bar'])
        self.assertEqual(obj.thing.spam, d['spam'])

    def test_unpack_keys_for_loop(self):
        results = []
        for x, y in unpack_keys([
            dict(x=1, y=2),
            dict(x=3, z=4),
            dict(a=5, y=6),
            dict(b=7, c=8),
        ], default=999):
            results.append((x, y))
        self.assertEqual(results, [
            (1, 2),
            (3, 999),
            (999, 6),
            (999, 999),
        ])

    def test_unpack_keys_list_comprehension(self):
        self.assertEqual(
            [(y, x) for x, y in unpack_keys([
                dict(x=1, y=2),
                dict(x=3, y=4),
            ])],
            [
                (2, 1),
                (4, 3),
            ])

    def test_unpack_keys_bigger_expression(self):
        x, y = map(int, unpack_keys(dict(x='1', y='2')))
        self.assertEqual(x, 1)
        self.assertEqual(y, 2)

    def test_unpack_attrs(self):
        obj = SimpleNamespace(aa='bv', bb='cc', cc='aa')
        cc, bb, aa = unpack_attrs(obj)
        self.assertEqual(aa, obj.aa)
        self.assertEqual(bb, obj.bb)
        self.assertEqual(cc, obj.cc)

    def test_print_args(self):
        out = StringIO()
        x = 3
        y = 4
        print_args(x + y,
                   x * y,
                   x -
                   y, file=out)
        self.assertEqual('''\
x + y =
7

x * y =
12

x -
                   y =
-1

''', out.getvalue())

    def test_dict_of(self):
        a = 1
        obj = SimpleNamespace(b=2)
        self.assertEqual(spells.dict_of(
            a, obj.b,
            c=3, d=4
        ), dict(
            a=a, b=obj.b,
            c=3, d=4))

    def test_no_starargs_in_dict_of(self):
        args = [1, 2]
        with self.assertRaises(TypeError):
            spells.dict_of(*args)

    def test_delegation(self):
        lst = MyListWrapper([1, 2, 3])
        lst.append(4)
        lst.extend([1, 2])
        lst = (lst + [5]).copy()
        self.assertEqual(type(lst), MyListWrapper)
        self.assertEqual(lst, [1, 2, 3, 4, 1, 2, 5])

    def test_magic_kwargs(self):
        foo = Foo()
        x = 1
        y = 2
        self.assertEqual(foo.bar(x, y, z=3),
                         {('x', x), ('y', y), ('z', 3), foo})

    def test_maybe(self):
        n = None
        assert maybe(n) is None
        assert maybe(n).a.b.c()[4]().asd.asd()() is None
        assert maybe(0) is 0
        assert maybe({'a': 3})['a'] is 3
        assert maybe({'a': {'b': 3}})['a']['b'] is 3
        assert maybe({'a': {'b': 3}})['a']['b'] + 2 == 5
        assert maybe({'a': {'b': None}})['a']['b'] is None

    def test_select_from(self):
        conn = sqlite3.connect(':memory:')
        c = conn.cursor()
        c.execute('CREATE TABLE points (x INT, y INT)')
        c.execute("INSERT INTO points VALUES (5, 3), (8, 1)")
        conn.commit()

        assert [(3, 5), (1, 8)] == [(y, x) for y, x in spells.select_from('points')]
        y = 1
        x = spells.select_from('points', where=[y])
        assert (x, y) == (8, 1)

    def test_multiple_attr_calls(self):
        x = 3
        y = 5
        self.assertEqual([
            spells.dict_of(x),
            spells.dict_of(y),
        ], [dict(x=x), dict(y=y)])

        with self.assertRaises(ValueError):
            print([spells.dict_of(x), spells.dict_of(y)])

    def test_no_assignment(self):
        with self.assertRaises(TypeError):
            unpack_keys(dict(x=1, y=2))

    def test_resolve_var(self):
        x = 8
        frame = inspect.currentframe()
        self.assertEqual(_resolve_var(frame, 'x'), x)
        with self.assertRaises(NameError):
            _resolve_var(frame, 'y')

    def test_spell_repr(self):
        self.assertRegex(repr(spells.dict_of),
                         r'Spell\(<function dict_of at 0x.+>\)')


if __name__ == '__main__':
    unittest.main()
