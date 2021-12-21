Exceptions
--------------------------------

.. module:: exceptions

.. class:: NoMatchError

    Raised by :meth:`.Setting.get` when a setting without a default value has no rule matching its context.

    Subclasses :class:`Exception`.