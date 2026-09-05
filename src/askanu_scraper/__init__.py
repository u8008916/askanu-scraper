"""
askanu_scraper — AskANU approved-source scraper package.

Pipeline: FETCH -> PARSE -> VALIDATE -> SANITY CHECK -> COMPARE
         -> DB UPDATE -> EMBED CHANGED -> MARK INDEXED -> PUBLISH CURRENT

Failure must preserve last-known-good data.
"""
