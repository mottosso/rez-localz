<img width=300 src=https://user-images.githubusercontent.com/2152766/60191937-07018080-982d-11e9-971b-43e2dbc75963.png>

Package localisation for Rez.

- [ ] [Design Document for 1.0](https://github.com/mottosso/rez-localz/issues/1)

**See also**

- [rez-pipz](https://github.com/mottosso/rez-pipz)
- [rez-scoopz](https://github.com/mottosso/rez-scoopz)

<br>

### What is "localisation"?

> **Localise** - To make something remote local

Once local, access to a given package no longer requires access to the original (e.g. network) location and yields performance equivalent to that of local access, such as from your SSD. SSDs typically read at 100-500mb/sec, with some capable of 1GB+/sec. NVRAM disks are even quicker, making network access akin to sending physical letters compared to email.

##### Example

Localisation is already possible with Rez like this.

```bash
$ export REZ_LOCAL_PACKAGES_PATH=~/packages
$ rez cp packageA-1.0.0 --dest-path=$REZ_LOCAL_PACKAGES_PATH
```

Now version `packageA-1.0.0` is "localised", in that it is accessible from a local directory, as opposed to wherever it came from. Assuming `REZ_LOCAL_PACKAGES_PATH` is first in `REZ_PACKAGES_PATH`, this package would get picked up first.

This project is an extension of this, with additional features such as:

- [x]  **Full Context Localisation** Take an entire context into account, with any number of requests, for maximum performance.
- [x]  **Solved Request Localisation** Unlike `rez cp`, requests made to `localised` are resolved prior to being copied
- [x]  **Multiple Package Localisation** That each resolve into the same context prior to localising, without taking dependencies with them
- [x]  **Respects `is_relocatable` flag** Packages have a `is_relocatable` variable that is respected by this mechanism, overridden with `--force`
- [x]  **Filtered Requests** Localise some packages in the context of other packages, for fine-grained control over what stays remote and what goes along for the ride.
- [x] **Multi Variant Localisation** Localise relevant or all variants for a package with the `--all-variants` flag, such that e.g. both `maya-2018` and `maya-2019` variants of a given plug-in is made available locally.
- [ ] [**Tagged Localisation**](https://github.com/mottosso/rez-localz/issues/5) Localised packages carry a special variable that identify them as having been localised, for future flags such as `rez env --no-localised`
- [ ] [**Automatic Localisation**](https://github.com/mottosso/rez-localz/issues/6) Based on various criteria
- [ ] **Software Provisioning** Replace your Ansible/Salt/Puppet stack with Rez for provisioning of large-scale software like Maya and Nuke, with the same familiar interface, version control and dependency resolution as any other Rez package
- [ ] **Distributed Asset Collaboration** Share and collaborate on assets with a remote workforce without the drag of VPNs or remote desktops
- [ ] **Secure Distributions** Collaborate with others using the same proprietary software, without risking your IPs or competative advantage

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
$ rez env localz -- localise mypackage
```

The package `mypackage` would then be localised to `~/.packages`.

##### Customise Destination

Localised packages default to `~/.packages`, which resides next to your "local" a.k.a. "development" package path, `~/packages`. Customise the destination path using either an environment variable or command-line argument.

```bash
$ export REZ_LOCALISED_PACKAGES_PATH=~/localised_packages
$ rez env localz -- localise Qt.py --prefix "~/localised_packages"
```

The argument takes precedence over the environment variable.

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

##### All Variants

Pass `--all-variants` to include every variant for a given package, rather than the one that matches the current resolve.

```bash
$ rez env localz -- localise python --all-variants
```

The above could include both Linux and Windows variants for the latest version of `python`.

<br>

### FAQ

##### <blockquote>What about <code>rez cp</code>?</blockquote>

`localise` uses `rez cp` under the hood and can be considered high-level version of it, taking more variables into account like context and other packages.