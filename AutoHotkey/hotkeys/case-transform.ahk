; Win+Ctrl+letter — transform selected text in place (see README).
; Modifiers are released before copy/paste so Send ^c is not Win+Ctrl+C.

#UseHook

#^u::CaseTransform(StrUpper)
#^l::CaseTransform(StrLower)
#^t::CaseTransform(ToTitleEachWord)
#^r::CaseTransform(ToRandomCase)
#^s::CaseTransform(ToSlug)

CaseTransform(transformFn, *) {
  TransformSelection(transformFn)
}
