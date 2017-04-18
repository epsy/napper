======
napper
======

.. image:: https://badges.gitter.im/epsy/napper.svg
   :alt: Join the chat at https://gitter.im/epsy/napper
   :target: https://gitter.im/epsy/napper?utm_source=badge&utm_medium=badge&utm_campaign=pr-badge&utm_content=badge
.. image:: https://travis-ci.org/epsy/napper.svg?branch=master
   :target: https://travis-ci.org/epsy/napper
.. image:: https://coveralls.io/repos/github/epsy/napper/badge.svg?branch=master
   :target: https://coveralls.io/github/epsy/napper?branch=master

A REST framework for asyncio.

Currently in experimental stage. Use at your own risk.

.. code:: python

    import asyncio

    from napper.apis import github

    async def getstargazers():
        """Print the most popular repository of the authors of
        the most recent gists from github."""
        async with github() as site:
            async for gist in site.gists.get():
                try:
                    repo = await gist.owner.repos_url.get()[0]
                except AttributeError:
                    print("{0.id}: Gist has no owner".format(gist))
                    continue
                except IndexError:
                    print("{0.id}: {0.owner.login} has no repositories".format(gist))
                    continue
                print("{0.id}: {0.owner.login} {1.name} {1.stargazers_count}".format(
                    gist, repo
                    ))

    loop = asyncio.get_event_loop()
    loop.run_until_complete(getstargazers())


.. image:: https://badges.gitter.im/epsy/napper.svg
   :alt: Join the chat at https://gitter.im/epsy/napper
   :target: https://gitter.im/epsy/napper?utm_source=badge&utm_medium=badge&utm_campaign=pr-badge&utm_content=badge