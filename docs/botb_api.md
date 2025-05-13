# Battle of the Bits API overview

This page serves as a general introduction to concepts used in the Battle of the Bits API, with information useful both for pyBotB users and anyone else wanting to add support for it. For official documentation, see ["BotB API v1" on the Lyceum](https://battleofthebits.com/lyceum/View/BotB+API+v1).

## Overview

The BotB API base URL is `https://battleofthebits.com/api/v1/`. The API URLs follow the following format:

```
https://battleofthebits.com/api/v1/{object_type}/{command}/...
```

For a list of object types, see [Object types](#object-types).

For most object types, the available commands are:

* **`/api/v1/{object_type}/load/{id}`** - retrieves an object by its ID (`id` property).
* **`/api/v1/{object_type}/list/[{page_number=0}/{page_length=25}]`** - retrieves multiple objects at once; also accepts filters, conditions and sorting options. Pagination is optional.
* **`/api/v1/{object_type}/random`** - gets a random object of this type.
* **`/api/v1/{object_type}/search/{query}`** - search for objects whose name/title contains the provided query string; only available for object types with a name/title attribute.

Some object types have additional endpoints; a full list can be fetched through [the API's documentation index](https://battleofthebits.com/api/v1/documentation/index). The documentation index also contains all possible properties that object types can have (with *some* caveats - see [Documentation index quirks](#documentation-index-quirks)).

```{note}
Make sure to use HTTPS for all API queries!
```

### Getting responses in XML format

The BotB API returns data in **JSON** format by default; it is also possible to get data in XML by adding `?format=xml` to the URL or adding the `.xml` extension to the URL. (TODO - verify which endpoints this works for)

## Object types

Available object types are:

* `battle` - a battle, either a major battle or an X Hour Battle (XHB).
* `botbr` - a BotBr, user of the site.
* `botbr_points` - the points for a BotBr for a specific class.
* `entry` - an entry, a single submission to a battle.
* `favorite` - a single favorite on an entry.
* `format` - a battle format.
* `group_thread` - a thread of messages; forum threads and comments on entries/battles/BotBr profiles are group threads.
* `lyceum_article` - an article on the Lyceum.
* `palette` - an on-site color palette.
* `playlist` - a single playlist containing entries.
  * `playlist_to_entry` - join table joining playlist and entry.
* `tag` - a single tag given to an entry.
* `botbr_stats` - a single statistic for a BotBr.
* `daily_stats` - the site-wide statistic for a specific day.

For an overview of properties for each object type, see pyBotB's implementation: [Data classes](/usage/data_classes.html).

## Basic commands

All object commands have at least 3 of the 4 basic commands: `load`, `list`, `random` and `search`. The following is a table of available basic commands per object type:

| Object type			| Load | List | Random | Search |
|-----------------------|------|------|--------|--------|
| `battle`				| ✔    | ✔    | ✔      | ✔      |
| `botbr`				| ✔    | ✔    | ✔      | ✔      |
| `botbr_points`		| ✔    | ✔    | ✔      | ✘      |
| `entry`				| ✔    | ✔    | ✔      | ✔      |
| `favorite`			| ✔    | ✔    | ✔      | ✘      |
| `format`				| ✔    | ✔    | ✔      | ✘      |
| `group_thread`		| ✔    | ✔    | ✔      | ✔      |
| `lyceum_article`		| ✔    | ✔    | ✔      | ✔      |
| `palette`				| ✔    | ✔    | ✔      | ✘      |
| `playlist`			| ✔    | ✔    | ✔      | ✔      |
| `playlist_to_entry`	| ✔*   | ✔    | ✔      | ✔      |
| `tag`					| ✔    | ✔    | ✔      | ✔      |
| `botbr_stats`			| ✔*   | ✔    | ✔      | ✘      |
| `daily_stats`			| ✔    | ✔    | ✔      | ✘      |

\* does not have an user-exposed ID, thus the load option is not very useful

### Load (`/api/v1/{object_type}/load/{id}`)

> `GET` `/api/v1/{object_type}/load/{id}`
>
> Load a single object by its ID.

**URL parameters:**

* `object_type` (str) - object type to perform the query for.
* `id` (int) - ID of the object that will be fetched.

**Returns:**

* **On success:** (HTTP `200`) - JSON-encoded object data.
* **On failure:**
  * **Not found:** (HTTP `500`) - JSON response:
    ```json
	{"response_type":"FAIL","response_message":"Object of type '{object_type}' with id '{id}' unfounded."}
	```
  * **Other server errors:** (HTTP `500`)

```{note}
Be aware that the "not found" error has HTTP status code 500, not 404!
```

---

### List (`/api/v1/{object_type}/list`)

> `GET` `/api/v1/{object_type}/list[/{page_number}[/{page_length}]][?sort={key}&desc=true&filters={key}~{val}^{key2}~{val2}]`
>
> Load a single object by its ID.

**Parameters:**

* `object_type` (str) - object type to perform the query for.
* `id` (int) - ID of the object that will be fetched.
* `page_number` (int, optional, default = `0`) - number of the page, for pagination.
* `page_length` (int, optional, default = `25` max. = `500`) - length of a single page, for pagination.

**URL parameters:**

* `sort` (str) - key to sort by.
* `desc` (bool, default = `false`) - if `true`, sort in descending order by the key specified in `sort`. Has no effect if `sort` is not set.
* `filters` (custom format) - perform an exact match on the given key's value. The format for a filter is `{key}~{val}`; multiple filters can be joined together with `^`, e.g. `{key1}~{val1}^{key2}~{val2}`.
  * A more powerful alternative to filters are **conditions** - see below.

**Returns:**

* **On success:** (HTTP `200`) - list of object data dicts; the list is empty if no objects match.
* **On failure:**
  * **Malformed parameters** (HTTP `400`) - plain-text error message, followed by `<br><br><i><b>Please RTFM</b></i><br><a href="https://battleofthebits.com/lyceum/View/BotB+API+v1/">https://battleofthebits.com/lyceum/View/BotB+API+v1/</a>`
  * **Server error** (HTTP `500`)

#### List conditions

**Conditions** are a more powerful alternative to filters; they allow for performing a subset of SQL-like filters on the query.

JSON-encoded conditions look as follows:

```js
"conditions": [
	{"property": "(property)", "operator": "(operator)", "operand": (operand)}
]
```

where `property` is the property to filter to, `operator` is the operator, and `operand` is the value passed through the operator.

All conditions have to be met for an item to match (think of it like an `AND` match).

```{note}
Some API queries within the site's client-side JS also provide a "key" property (usually set to the same value as "property"); however, it appears to be unused and can safely be ignored (TODO?).
```

**Available operators:**

* `=` - check if the value of the property equals the operand. **Only works with numerical operands** (returns "non numeric operand must use different operator" error otherwise); for strings, use `LIKE` instead.
* `<>` - check if the value of the property does not equal the operand. **Only works with numerical operands** (returns "non numeric operand must use different operator" error otherwise); for strings, use `NOT LIKE` instead.
* `<`, `>`, `<=`, `>=` - standard mathematical checks; **only work with numerical operands**.
* `&` - binary AND operator; **only works with numerical operands**.
* `LIKE`/`NOT LIKE` - check if the **string** value of the property matches the operand. The operand is either:
  * The string itself for an exact match (e.g. `weave`);
  * The string prepended/appended with `%` to perform a glob.
    * `%ve` will match `weave` and `eve`,
    * `dream%` will match `dreamghost.it`,
    * `%dad%` will match `dads`, `asdad`, `qwertydaduiop`
* `IN` - check if the value of the property is contained within the list provided in the operand. **The operand must be a list of values.**
* `IN_SUBQUERY:{subquery}` - exact mechanics are not known yet. Known subqueries are:
  * On `/api/v1/entry/list`:
    * `id`, `IN_SUBQUERY:botbr_entry_list`, `{botbr_id}` (prop, operator, operand) - returns entries which the BotBr either submitted or was added as a colaborator on. Used on the Entries page of a BotBr's profile.
    * `id`, `IN_SUBQUERY:botbr_favorites`, `{botbr_id}` (prop, operator, operand) - returns the favorite entries of the BotBr with the given ID. Used on the Favorites page of a BotBr's profile.
* `IS`/`IS NOT` - can be used in combination with an operand of `NULL` or `NOT NULL` to check if a field is/is not NULL. All other operands are not allowed.

##### Sending list conditions

**Sending conditions** is done by sending an **AJAX `POST`** request with the conditions passed in the `conditions` property (and optionally with `sort` and `desc` included). **Filters are ignored when passing conditions.**

In jQuery, this request can be prepared as such:

```js
$.ajax({
	type: "POST",
	url: "https://battleofthebits.com/api/v1/{object_type}/list",
	data: {
		conditions: [
			{property: "property1", operand: "<>", operator: "operator1"},
			{property: "property2", operand: "<>", operator: "operator2"},
			/* ... */
		],
		/* optionally: */
		sort: "id",
		desc: true
	}
});
```

In other languages - you must send a `POST` request, the `Content-Type` header must be set to `multipart/form-data`, and the data must be sent in **form data** format. The conditions list must then be converted into the following format:

```
conditions[0][property]=property1
conditions[0][operand]=<>
conditions[0][operator]=operator1

conditions[1][property]=property2
conditions[1][operand]=LIKE
conditions[1][operator]=operator2

...

conditions[{n}][property]=...
conditions[{n}][operand]=...
conditions[{n}][operator]=...
```

For cases where the operator is a list (`IN` operand), it must be passed like so:

```
conditions[{n}][operator][0]=val1
conditions[{n}][operator][1]=val1

...

conditions[{n}][operator][{i}]=valI
```

```{note}
Most HTTP request libraries, upon being passed a dictionary-like object, will attempt to send JSON data raw, using the `application/json` content type. **This is not supported by the BotB API** and your arguments will be ignored. You **must** use the method described above.
```

---

### Random `/api/v1/{object_type}/random`

> `GET` `/api/v1/{object_type}/random`
>
> Load a random object with the given object type.

**Parameters:**

* `object_type` (str) - object type to perform the query for.

**Returns:**

* **On success:** (HTTP `200`) - list containing a single object data dict. (TODO - is it possible to get multiple values?)
* **On failure:**
  * **Server error** (HTTP `500`)

---

### Search `/api/v1/{object_type}/search/{query}`

> `GET` `/api/v1/{object_type}/search/{query}[/{page_number}[/{page_length}]]`
>
> Search for objects of the given type whose name/title property contains the query
> substring.
>
> This command is only available for objects with a title/name or equivalent attribute.

**Parameters:**

* `object_type` (str) - object type to perform the query for.
* `query` (str) - Substring to find in the names. Case-insensitive, matches inside of the title as well.
* `page_number` (int, optional, default = `0`) - number of the page, for pagination.
* `page_length` (int, optional, default = `25` max. = `500`) - length of a single page, for pagination.

**Returns:**

* **On success:** (HTTP `200`) - list containing the matching objects; empty if no results were found.
* **On failure:**
  * **Malformed parameters** (HTTP `400`) - plain-text error message, followed by `<br><br><i><b>Please RTFM</b></i><br><a href="https://battleofthebits.com/lyceum/View/BotB+API+v1/">https://battleofthebits.com/lyceum/View/BotB+API+v1/</a>`
  * **Server error** (HTTP `500`)

## Object type-specific commands

Some object types also implement additional commands. These are outlined in this section.

### Battle (`battle`)

#### Current battles (`/api/v1/battle/current`)

> `GET` `/api/v1/battle/current`
>
> Get a list of upcoming and ongoing battles.

**Returns:**

* **On success:** (HTTP `200`) - list containing upcoming and ongoing battles.
* **On failure:**
  * **Server error** (HTTP `500`)

---

#### List by date (`/api/v1/battle/list_by_date/{date}`)

> `GET` `/api/v1/battle/list_by_date/{date}`
>
> Get a list of all battles that happened on this date (date in YYYY-MM-DD format).

**Parameters:**

* `date` (str) - date in `YYYY-MM-DD` (EST timezone).

**Returns:**

* **On success:** (HTTP `200`) - list containing battles that happened on the requested date.
* **On failure:**
  * **Malformed parameters** (HTTP `400`) - plain-text error message, followed by `<br><br><i><b>Please RTFM</b></i><br><a href="https://battleofthebits.com/lyceum/View/BotB+API+v1/">https://battleofthebits.com/lyceum/View/BotB+API+v1/</a>`
  * **Server error** (HTTP `500`)

---

#### List by month (`/api/v1/battle/list_by_month/{date}`)

> `GET` `/api/v1/battle/list_by_month/{date}`
>
> Get a list of all battles that happened during this month (date in YYYY-MM format).

**Parameters:**

* `date` (str) - date in `YYYY-MM` (EST timezone).

**Returns:**

* **On success:** (HTTP `200`) - list containing battles that happened during the requested month.
* **On failure:**
  * **Malformed parameters** (HTTP `400`) - plain-text error message, followed by `<br><br><i><b>Please RTFM</b></i><br><a href="https://battleofthebits.com/lyceum/View/BotB+API+v1/">https://battleofthebits.com/lyceum/View/BotB+API+v1/</a>`
  * **Server error** (HTTP `500`)

---

### BotBr (`botbr`)

#### Get level-up points (`/api/v1/botbr/levels`)

> `GET` `/api/v1/botbr/levels`
>
> Get a list where the index is the level, and the value is the amount of
> points required to reach that level.

**Returns:**

* **On success:** (HTTP `200`) - list containing level-up point requirements.
* **On failure:**
  * **Server error** (HTTP `500`)

---

### Entry (`entry`)

#### Battle activity list (`/api/v1/entry/battle_activity_playlist`)

> `GET` `/api/v1/entry/battle_activity_playlist`
>
> Get a list of the last 40 winning entries in battles ("battle activity" box
> on main page).

**Returns:**

* **On success:** (HTTP `200`) - list containing winning entries.
* **On failure:**
  * **Server error** (HTTP `500`)

---

#### Entry activity list (`/api/v1/entry/entry_activity_playlist`)

> `GET` `/api/v1/entry/entry_activity_playlist`
>
> Get a list of the last 40 submitted entries ("entry activity" box on main
> page).

**Returns:**

* **On success:** (HTTP `200`) - list containing recent entries.
* **On failure:**
  * **Server error** (HTTP `500`)

---

#### Playlist entries (`/api/v1/entry/playlist_playlist/{playlist_id}`)

> `GET` `/api/v1/entry/playlist_playlist/{playlist_id}`
>
> List all entries in the playlist with the given ID.

**Parameters:**

* `playlist_id` (int) - ID of the playlist to get the entries of.

**Returns:**

* **On success:** (HTTP `200`) - list containing recent entries.
* **On failure:**
  * **Playlist not found:** (HTTP `500`) - empty response (0 bytes).
  * **Server error** (HTTP `500`)

---

#### BotBr favorites (`/api/v1/entry/botbr_favorites_playlist/{botbr_id}`)

> `GET` `/api/v1/entry/playlist_playlist/{botbr_id}`
>
> List all favorite entries of the BotBr with the given ID.

```{note}
This seems to be missing some favorites; to get an accurate list, do a query
to `/api/v1/entry/list` with the following condition: ("id", "IN_SUBQUERY:botbr_favorites",
(BotBr ID)) (property, operator, operand).
```

**Parameters:**

* `botbr_id` (int) - ID of the BotBr to get the favorites of.

**Returns:**

* **On success:** (HTTP `200`) - list containing recent entries.
* **On failure:**
  * **Playlist not found:** (HTTP `500`) - empty response (0 bytes).
  * **Server error** (HTTP `500`)

---

#### Covers/entries covered in Decadent Decade battles (`/api/v1/entry/decadent_covered`)

> `GET` `/api/v1/entry/decadent_covered`
>
> List all cover entries and original entries that were covered in
> Decadent Decade cover battles.

```{note}
The first entry is covered, the rest are covers...? TODO
```

**Returns:**

* **On success:** (HTTP `200`) - list containing entries.
* **On failure:**
  * **Server error** (HTTP `500`)

---

### Tag (`tag`)

#### Tag cloud by substring (`/api/v1/tag/cloud_by_substring/{substring}`)

> `GET` `/api/v1/tag/cloud_by_substring/{substring}`
>
> Get a HTML representation of a tag cloud containg clouds matching the given
> substring.

**Parameters:**

* `substring` (str) - Substring to find in tags.

**Returns:**

* **On success:** (HTTP `200`) - list containing a single string with HTML representation of tag word cloud.
* **On failure:**
  * **Server error** (HTTP `500`)

---

### Palette

#### Get current default palette (`/api/v1/palette/current_default`)

> `GET` `/api/v1/palette/current_default`
>
> Get the current default on-site palette.

**Returns:**

* **On success:** (HTTP `200`) - list containing a single palette object representing the current default palette.
* **On failure:**
  * **Server error** (HTTP `500`)

---

### BotBr stats (`botbr_stats`)

#### BotBr stats by BotBr ID (`/api/v1/botbr_stats/by_botbr_id/{botbr_id}`)

> `GET` `/api/v1/botbr_stats/by_botbr_id/{botbr_id}`
>
> List all BotBr stats for the BotBr with the given ID.

**Parameters:**

* `botbr_id` (int) - ID of the BotBr to fetch the stats for.

**Returns:**

* **On success:** (HTTP `200`) - list containing BotBr statistics table entries.
* **On failure:**
  * **Server error** (HTTP `500`)

---

#### BotBr stats by BotBr ID from the last N days (`/api/v1/botbr_stats/days_back/{botbr_id}/{n_days}`)

> `GET` `/api/v1/botbr_stats/days_back/{botbr_id}/{n_days}`
>
> List BotBr stats from the last n_days for the BotBr with the given ID.

**Parameters:**

* `botbr_id` (int) - ID of the BotBr to fetch the stats for.
* `n_days` (int) - the amount of days back for which to fetch the stats.

**Returns:**

* **On success:** (HTTP `200`) - list containing BotBr statistics table entries.
* **On failure:**
  * **Server error** (HTTP `500`)

---

### Other

#### List point types (`/api/v1/point/types`)

> `GET` `/api/v1/point/types`
>
> Get a list of point types (BotBr classes).

```{note}
There are glitched lowercase point types, as well as an empty point type,
that can be seen on the site; this endpoint **only returns normal, valid classes**,
and should not be treated as an absolute authority on the types of classes
you'll see in the wild.
```

**Returns:**

* **On success:** (HTTP `200`) - list containing point type/class names.
* **On failure:**
  * **Server error** (HTTP `500`)

---

#### Interpret Firki markup (`/api/v1/firki/interpret`)

> `POST` `/api/v1/firki/interpret`
>
> Interpret a Firki markup string into HTML.

**Post form data:**

- `firki_string` (str) - the string to convert. (Note that this string always ends with `</span>` (although no opening span tag is provided); you may want to remove it.)

* **On success:** (HTTP `200`) - JSON list with a single item, containing the interpreted text as a string.
* **On failure:**
  * **Server error** (HTTP `500`)

---

#### Spriteshit version (`/api/v1/spriteshit/version`)

> `GET` `/api/v1/spriteshit/version`
>
> Get the current version of BotB's icon spritesheet (affectionately
> named the "spriteshit").
>
> The spritesheet PNG can be fetched from the following URL:
> https://battleofthebits.com/styles/spriteshit/{version}.png

**Returns:**

* **On success:** (HTTP `200`) - JSON object with a single property named "spriteshit_version" containing the version as a string.
* **On failure:**
  * **Server error** (HTTP `500`)

---

## Known quirks

This is a WIP list of quirks with the BotB API and various objects that exist within BotB's nearly 20-year-old database. These are all worked around in pyBotB; they are listed here as they could be of interest to other API implementations.

* **Battle:** Battles fetched through the `/api/v1/battle/load` endpoint do not have `period` and `period_end(_*)` properties. If you need to access them, use the `list` endpoint with a filter to match for the ID.
  * This also applies to the `battle` object returned by `entry` APIs.
* **Battle:** Battles in the Tally Period do not return a `period` value (though they do have a `period_end` value).
* **Entry:** Some older entries do not have comment threads attached to them; for those entries, the `posts` property will be missing. If you depend on it being there, you can assume that a missing `posts` property is equivalent to a `posts` value of `0`.

### Documentation index quirks

If you plan to parse data using the documentation index, keep the following quirks in mind:

* `entry` object endpoints, besides containing the properties listed in the `properties` variable, also return `botbr`, `battle` and `format` properties, which contain the entry author's BotBr object, the battle object for the battle the entry was in, and the Format object for the entry's format respectively.
* `battle`.`disable_penalty` is not returned by the API.
* `group_thread`.`last_post_timestamp` is not returned by the API.

### TODO

Parts of the API that I have yet to figure out:

* `/api/v1/battle/entries_by_format` does not seem to return anything; likely someone needs to figure out the right parameters.
* `/api/v1/entry/botbr_favorites_playlist/{id}` does not return all favorites. TODO.
* Need to figure out how the top 40 endpoints are to be interpreted (`https://battleofthebits.com/api/v1/entry/top40_by_day_count`, `https://battleofthebits.com/api/v1/entry/top40majors`, `https://battleofthebits.com/api/v1/entry/top40minors`)
* Need to figure out how `https://battleofthebits.com/api/v1/entry/decadent_covered` works/where it's used
* Need to figure out what `/api/v1/points/type_m`/`type_medium` and `type_q`/`type_quality` mean
