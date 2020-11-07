* Finish existing tests
* Fill in the README
    - Mention all "decisions" e.g. default timeouts
    - Decision = test thoroughly with mocks + manual testing
    - Mention 100% test coverage + mypy type hints = how I achieved code quality
    - Chose to use click because it has testing functionality
    - Which error types are handled (and which aren't [e.g. invalid URL without 'http'?]) and why
    - Next step: custom limit
    - Next step: maybe handle more errors
    - Decision made: Round time to 3dp (explain in comment and README)
* Make sure requirements have all needed requirements and nothing else
* General clean up - e.g. tests which have just one URL don't use variable name "url_1"
* Docstrings for all tests and all methods
* Something which tells me why I have no metrics etc. if I have empty file / 1 URL
* Comment why time.monotonic
* Make mypy pass