Outdated Declarations
=========================

Heksher-py is prepared for your setting declarations to be outdated and overridden by a newer declaration, and strives
to be as backwards-compatible with newer declarations.

Default Value Changed
------------------------
If a default value for the server is different from the local declaration, the server's default is used (so long as it
is compatible with the setting's type, see :ref:`Rejecting_Values`).


Coercing Values
---------------------
Sometimes, the types of settings are upgraded in the server. This can lead to a situation where a rule value, or the
setting's default value is incompatible with the local declaration's type. In this case, heksher-py may attempt to
convert the value to the local declaration's type. These coercions, when they are possible, will almost always be with
some data loss. For more information about the various coercions, see :ref:`SettingType.Coercions <coercions>`.

If a coercion occurs, it will be logged.

Refusing coercions
^^^^^^^^^^^^^^^^^^^^
For some settings, we may want to avoid coercion. For example, if a setting is a mapping, then coercion will simply
discard any incompatible key-value pairs, and the setting might require that all the keys be present. In this case,
we can set a setting's :class:`~setting.Setting`'s ``on_coerce`` parameter to reject or even customize the behaviour of
coercions.

.. _rejecting_values:

Rejecting Values
---------------------
Sometimes coercion is not possible, and we want to reject the value. For example, if we declare a setting as a list,
but that declaration has already be overridden to be a string, then no coercion will be possible. In this case, we
simply discard the rule with the incompatible value, or disregard the default value. In either case, a message will
be logged.

.. note:: On ignoring server defaults

    If server's default value is ignored, then the setting's default value will first fall back not to the setting's
    local default value, but to the **last valid server default value**, if any exist.


Rejecting Rules
---------------------
Sometimes, a setting's configurable features change to subsets that the local declaration does not support. If any rule
relies on context features that are not in the local setting declaration's configurable features, then the rule will be
discarded with a log message.