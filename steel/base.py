import collections
import io
from gettext import gettext as _

from steel.decorators import classproperty, classinstancemethod


class NameAwareOrderedDict(collections.OrderedDict):
    _("""
    A custom namespace that not only orders its items, but can
    also make those items aware of their names immediately.
    It also helps maintain the list of fields in the stack.
    """)

    def __setitem__(self, name, obj):
        super(NameAwareOrderedDict, self).__setitem__(name, obj)
        if hasattr(obj, 'set_name'):
            obj.set_name(name)


class StructureMetaclass(type):
    @classmethod
    def __prepare__(cls, name, bases, **options):
        return NameAwareOrderedDict()

    def __new__(cls, name, bases, attrs, **options):
        # Nothing to do here, but we need to make sure options
        # don't get passed in to type.__new__() itself.
        return type.__new__(cls, name, bases, attrs)

    def __init__(cls, name, bases, attrs, **options):
        cls._fields = collections.OrderedDict()

        for name, attr in attrs.items():
            if hasattr(attr, 'attach_to_class'):
                attr.attach_to_class(cls)


class StructureBase:
    size = 0

    def __init__(self, **kwargs):
        # Values can be added explicitly
        for name, value in kwargs.items():
            setattr(self, name, value)

    # Marshal/Pickle API

    @classmethod
    def load(cls, fp):
        obj = cls()

        for name, field in cls._fields.items():
            value = field.read_value(fp)
            setattr(obj, name, value)

        return obj

    @classmethod
    def loads(cls, string):
        with io.BytesIO(string) as fp:
            return cls.load(fp)

    @classinstancemethod
    def dump(cls, self, fp):
        # This can be called either directly on a class or on one of its instances.
        # If on an instance, self is the instance itself, like usual; if called on
        # a class, self will be the first positional argument passed in instead.
        # This way, you can call obj.dump(fp), which is a more OO approach, or
        # or Structure.dump(obj, fp), which matches the standard dump/load API.

        for name, field in cls._fields.items():
            if name in self.__dict__:
                # Checking in the instance dictionary is necessary because
                # getattr() will fall back to class attributes and find fields
                value = getattr(self, name)
                field.write_value(fp, value)
            else:
                # At least try to write without a value, in case the field
                # has a default or can otherwise write what it needs to write
                field.write_value(fp)

    @classinstancemethod
    def dumps(cls, self):
        with io.BytesIO() as fp:
            cls.dump(self, fp)
            return fp.getvalue()

    @classmethod
    def has_default(cls):
        # A structure only has a default if all its fields have defaults
        return all(f.has_default() for f in cls._fields.values())

    @classproperty
    def default(cls):
        if self.has_default():
            values = dict((k, v.default) for (k, v) in cls._fields.items())
            return cls(**values)
        else:
            raise ValueError("No default available for %s structures" % cls.__name__)

    def __str__(self):
        return _('<Binary Data>')

    def __repr__(self):
        return '<%s: %s>' % (type(self).__name__, self)


class Structure(StructureBase, metaclass=StructureMetaclass):
    pass


class StructureTupleMetaclass(StructureMetaclass):
    def __init__(cls, name, bases, attrs, **options):
        super(StructureTupleMetaclass, cls).__init__(name, bases, attrs, **options)

        cls._namedtuple = collections.namedtuple(name, cls._fields.keys())


class StructureTuple(StructureBase, metaclass=StructureTupleMetaclass):
    def __new__(cls, **kwargs):
        data = (kwargs.get(name, None) for name in cls._fields)
        return cls._namedtuple(*data)

    @classinstancemethod
    def dump(cls, obj, fp):
        # Because __new__ returnes a namedtuple, it's not likely that this will
        # ever be called as an instance method, but we'll still plan for it.
        # Otherwise, we could simply have this be a classmethod.

        for name, field in cls._fields.items():
            # In this case, obj is expected to be a namedtuple, so getattr()
            # can't accidentally fall back onto class attributes.
            value = getattr(obj, name)
            field.write_value(fp, value)
