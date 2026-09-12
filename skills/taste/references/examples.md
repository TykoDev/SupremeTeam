# Taste examples

## Project preference

“Remember that I prefer compact tables in this project” routes through Admiral
to Taste. Taste selects project scope, records compact and spacious examples,
previews the project diff and effective profile, then writes the confirmed
explicit preference.

## Global preference

“Save this style globally” is an explicit global target, but Taste still previews
what other projects will inherit. If the style was inferred from casual praise,
Taste asks the user to confirm the normalized rule before persisting it.

## Consumption without mutation

“Design this dashboard” runs the normal design pipeline. The architect consumes
the resolved Taste handoff if present; this does not open Taste or create new
preferences. Likewise, invoking a browser or QA utility does not interpret
feedback as a Taste mutation.

## Promotion and destructive work

“Promote this project preference” produces a global diff and requires explicit
confirmation. “I don't love this screen” is never interpreted as promotion,
global reset, bulk import, or bulk revocation. “Forget preference `density` in
this project” may revoke that one named project entry; ambiguous or batch removal
is previewed and confirmed first.

## Accessibility conflict

If “always use pale gray text” conflicts with readable contrast, Taste reports
the accessibility problem and does not normalize it into a binding visual rule.
It asks whether the user instead wants a low-emphasis hierarchy that continues
to meet the project's accessibility requirements.
