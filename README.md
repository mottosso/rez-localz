<img width=300 src=https://user-images.githubusercontent.com/2152766/60191937-07018080-982d-11e9-971b-43e2dbc75963.png>

Package localisation for Rez.

**See also**

- [rez-pipz](https://github.com/mottosso/rez-pipz)
- [rez-scoopz](https://github.com/mottosso/rez-scoopz)

<br>

### Usage

![localz8](https://user-images.githubusercontent.com/2152766/60201451-35d52200-9840-11e9-8213-1a7448525470.gif)

**Prerequisities**

- `rez-2.29+`
- `python-2.7,<4`

Used as a Rez package.

```bash
$ git clone https://github.com/mottosso/rez-localz.git
$ cd rez-localz
$ rez build --install
```

Once installed, you can start localising packages like this.

```bash
$ rez env localz -- localise Qt.py
```

This will localise the [Qt.py]() package onto your `config.local_packages_path`.

##### Multiple requests

Localise multiple packages at once, that all resolve to one another making sure they work together.

```bash
$ rez env localz -- localise maya-2018 arnold flex
```

##### Full context

Localise an entire context with the `--full` flag.

```bash
$ rez env localz -- localise maya alita gitlab --full
```

##### Limited by requirements

Localise one package resolved with another.

```bash
$ rez env localz -- localise maya --requires alita
```

In this case, if `alita` carries a requirement for `maya-2018` then that's the version being localised, despite `maya-2017` and `maya-2019` also being available.

##### Specific localisation

The syntax to `localise` is the same as for `rez env`, including complex version queries.

```bash
$ rez env localz -- localise "maya-2015,<2020"
```

<br>

### FAQ

##### <blockquote>What about <code>rez cp</code>?</blockquote>

`localise` uses `rez cp` under the hood and can be considered high-level version of it, taking more variables into account like context and other packages.