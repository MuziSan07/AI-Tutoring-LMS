"""Seed catalogue for the demo academy: original tech & business courses.

Lessons are written with "## Example" and "## Key points" sections - the AI
tutor's offline mode uses them for "explain simply" and "give me an example".
Quiz questions are tagged with the concept they assess so mastery can be
tracked per concept.
"""


def L(title, kind, minutes, concepts, md, quiz=None, rubric=None, video=None):
    return {"title": title, "kind": kind, "minutes": minutes, "concepts": concepts, "md": md.strip(),
            "quiz": quiz, "rubric": rubric, "video": video}


def C(q, options, answer, concept, explain):
    return {"q": q, "type": "choice", "options": options, "answer": answer, "concept": concept, "explain": explain}


def S(q, accept, concept, explain, tolerance=None):
    return {"q": q, "type": "short", "accept": accept, "tolerance": tolerance, "concept": concept, "explain": explain}


PYTHON = {
    "slug": "python-for-beginners", "title": "Python for Beginners",
    "subtitle": "Write your first real programs - no experience needed",
    "description": "Learn to think like a programmer. You'll go from printing your first line of text to writing functions that work with lists and dictionaries, finishing with a small project you can show off.",
    "category": "Programming", "level": "Beginner", "colour": "#2563eb", "icon": "🐍",
    "outcomes": ["Store and change data with variables", "Make decisions with if / elif / else",
                 "Repeat work with for and while loops", "Write reusable functions",
                 "Organise data with lists and dictionaries"],
    "modules": [
        ("Getting started", [
            L("What is programming?", "article", 6, ["programs"], """
A **program** is a list of instructions a computer follows exactly, one after another. Python is popular for beginners because its instructions read almost like English.

Your first instruction is `print`, which shows text on the screen:

```python
print("Hello, world!")
```

Text inside quotes is called a **string**. Python runs your code from the top line to the bottom line, so the order of instructions matters.

## Example
```python
print("Step 1: boil the kettle")
print("Step 2: add the tea bag")
```
This prints two lines, in that order - just like following a recipe.

## Key points
- A program is a sequence of exact instructions.
- `print()` displays a value on screen.
- Text in quotes is a string.
- Python runs code top to bottom.
"""),
            L("Variables and data types", "article", 9, ["variables", "data-types"], """
A **variable** is a named box that stores a value so you can use it later. You create one with `=`:

```python
name = "Aisha"
age = 29
price = 4.99
is_member = True
```

Every value has a **type**: `str` for text, `int` for whole numbers, `float` for decimals and `bool` for `True`/`False`. You can check a type with `type(age)`.

The `=` sign means *assign*, not *equals*. `age = age + 1` takes the current value, adds one, and stores the result back in `age`.

You can't add a string to a number directly: `"Age: " + age` causes an error. Convert first with `str(age)`, or use an f-string: `f"Age: {age}"`.

## Example
```python
score = 10
score = score + 5
print(f"Your score is {score}")   # Your score is 15
```

## Key points
- Variables store values under a name.
- Main types: str, int, float, bool.
- `=` assigns a value; it does not test equality.
- Use f-strings to mix text and numbers.
"""),
            L("Quiz: Python basics", "quiz", 5, ["variables", "data-types", "programs"], "Check your understanding of the basics.", quiz=[
                C("What does `print(\"Hi\")` do?", ["Saves Hi to a file", "Shows Hi on the screen", "Creates a variable called Hi", "Deletes Hi"], 1, "programs",
                  "print() displays a value on the screen."),
                C("What type is the value `4.99`?", ["int", "str", "float", "bool"], 2, "data-types",
                  "Numbers with a decimal point are floats."),
                S("After `x = 3` and then `x = x + 4`, what is the value of x?", ["7"], "variables",
                  "x starts as 3, then x + 4 = 7 is stored back into x."),
                C("Which line correctly combines text and a number?", ['"Age: " + 30', 'f"Age: {30}"', '"Age: " - 30', 'print Age 30'], 1, "data-types",
                  "An f-string converts the number to text for you. Adding a string and an int raises a TypeError."),
            ]),
        ]),
        ("Making decisions and repeating", [
            L("If statements", "article", 8, ["conditionals"], """
Programs often need to choose what to do. An **if statement** runs a block of code only when a condition is `True`:

```python
temperature = 28
if temperature > 25:
    print("Wear sunscreen")
elif temperature > 15:
    print("A light jacket is fine")
else:
    print("Wrap up warm")
```

Python checks each condition in order and runs only the **first** block that matches. The indentation (four spaces) shows which lines belong to each block - Python is strict about this.

Comparison operators: `==` (equal to), `!=` (not equal), `>`, `<`, `>=`, `<=`. Combine conditions with `and`, `or` and `not`.

## Example
```python
age = 17
if age >= 18:
    print("You can vote")
else:
    print(f"You can vote in {18 - age} year(s)")
```

## Key points
- `if` runs code only when its condition is True.
- `elif` and `else` handle the other cases; only the first match runs.
- Use `==` to compare, `=` to assign.
- Indentation defines the block.
"""),
            L("Loops", "article", 10, ["loops"], """
A **loop** repeats code so you don't have to write it many times.

A **for loop** runs once for every item in a sequence:

```python
for fruit in ["apple", "banana", "cherry"]:
    print(fruit)
```

`range(5)` produces the numbers 0, 1, 2, 3, 4 - it starts at 0 and stops *before* 5. So `for i in range(5)` repeats 5 times.

A **while loop** repeats as long as a condition stays True:

```python
count = 3
while count > 0:
    print(count)
    count = count - 1
print("Lift off!")
```

Be careful: if the condition never becomes False you get an **infinite loop**. Always make sure something inside the loop moves it towards stopping.

## Example
Adding up the numbers 1 to 100:
```python
total = 0
for n in range(1, 101):
    total = total + n
print(total)   # 5050
```

## Key points
- `for` loops over each item in a sequence.
- `range(n)` gives 0 up to n-1.
- `while` repeats while a condition is True.
- Make sure while loops can end.
"""),
            L("Quiz: decisions and loops", "quiz", 6, ["conditionals", "loops"], "Test yourself on if statements and loops.", quiz=[
                C("Which operator checks if two values are equal?", ["=", "==", "!=", "=>"], 1, "conditionals",
                  "`==` compares values; a single `=` assigns."),
                S("How many times does `for i in range(4):` repeat?", ["4", "four"], "loops",
                  "range(4) gives 0, 1, 2, 3 - four values."),
                C("With temperature = 20, what prints?\n```python\nif temperature > 25: print('Hot')\nelif temperature > 15: print('Mild')\nelse: print('Cold')\n```",
                  ["Hot", "Mild", "Cold", "Mild and Cold"], 1, "conditionals",
                  "20 is not > 25, but it is > 15, so the elif runs and the rest is skipped."),
                C("What is the main risk with a while loop?", ["It runs only once", "It can never use variables", "It may never stop", "It is slower than print"], 2, "loops",
                  "If the condition never becomes False, the loop runs forever."),
            ]),
        ]),
        ("Functions and collections", [
            L("Functions", "article", 10, ["functions"], """
A **function** is a named, reusable block of code. You define it once with `def` and call it as many times as you like:

```python
def greet(name):
    return f"Hello, {name}!"

message = greet("Sam")
print(message)
```

`name` is a **parameter** - a placeholder for the value you pass in (the **argument**). `return` sends a result back to whoever called the function. A function without `return` gives back `None`.

Functions make code shorter, easier to test and easier to read. A good function does **one job** and has a name that says what that job is.

## Example
```python
def vat_inclusive(price, rate=0.2):
    return round(price * (1 + rate), 2)

print(vat_inclusive(10))        # 12.0
print(vat_inclusive(10, 0.05))  # 10.5
```
`rate=0.2` is a default value used when no rate is given.

## Key points
- Define with `def name(parameters):`.
- `return` sends a value back.
- Parameters can have default values.
- One function, one job.
"""),
            L("Lists and dictionaries", "article", 12, ["lists", "dictionaries"], """
A **list** stores items in order. Items are accessed by position, starting at **0**:

```python
tasks = ["email", "meeting", "report"]
print(tasks[0])      # email
tasks.append("gym")  # add to the end
print(len(tasks))    # 4
```

A **dictionary** stores **key: value** pairs, so you look things up by name instead of position:

```python
prices = {"coffee": 2.5, "tea": 2.0}
print(prices["tea"])     # 2.0
prices["cake"] = 3.25    # add a new pair
```

Use a list when order matters and items are similar. Use a dictionary when each value has a label.

## Example
Looping over a dictionary:
```python
for item, price in prices.items():
    print(f"{item}: £{price}")
```

## Key points
- Lists are ordered and indexed from 0.
- `append` adds to a list; `len` counts items.
- Dictionaries map keys to values.
- `.items()` loops over key-value pairs.
"""),
            L("Quiz: functions and collections", "quiz", 6, ["functions", "lists", "dictionaries"], "Check you're ready for the project.", quiz=[
                C("What keyword sends a value back from a function?", ["print", "send", "return", "def"], 2, "functions",
                  "`return` hands a value back to the caller; print only displays it."),
                S("For `colours = ['red', 'green', 'blue']`, what is `colours[1]`?", ["green", "'green'", '"green"'], "lists",
                  "Lists start at index 0, so index 1 is the second item: green."),
                C("Which is the best structure to store a product name with its price?", ["A list", "A dictionary", "A string", "A bool"], 1, "dictionaries",
                  "A dictionary labels each value: {'coffee': 2.5}."),
                S("What does `len(['a', 'b', 'c'])` return?", ["3", "three"], "lists",
                  "len counts the items in the list: 3."),
            ]),
            L("Project: shopping basket calculator", "assignment", 25, ["functions", "lists", "dictionaries", "loops"], """
Put everything together. Write a program that:

1. Stores product prices in a **dictionary**.
2. Stores a customer's basket as a **list** of product names.
3. Uses a **function** called `basket_total(basket, prices)` that **loops** over the basket and **returns** the total.
4. Prints the total, and prints "Free delivery!" **if** the total is over £20.

Paste your code below with a short explanation of how it works.
""", rubric=[
                {"criterion": "Uses a dictionary for prices", "keywords": ["{", ":"], "tip": "Store prices like {'apple': 0.5}."},
                {"criterion": "Defines a function with def", "keywords": ["def "], "tip": "Wrap the total calculation in def basket_total(...)."},
                {"criterion": "Loops over the basket", "keywords": ["for "], "tip": "Use a for loop to visit each item."},
                {"criterion": "Returns the total", "keywords": ["return"], "tip": "Your function should return the total, not just print it."},
                {"criterion": "Applies the free-delivery rule", "keywords": ["if ", "20"], "tip": "Add an if statement checking whether the total is over 20."},
            ]),
        ]),
    ],
}

MARKETING = {
    "slug": "digital-marketing-fundamentals", "title": "Digital Marketing Fundamentals",
    "subtitle": "Attract, convert and measure customers online",
    "description": "A practical introduction to how businesses grow online: understanding the funnel, search engine optimisation, social and paid channels, and the numbers that tell you what's working.",
    "category": "Marketing", "level": "Beginner", "colour": "#db2777", "icon": "📣",
    "outcomes": ["Map a customer journey with the marketing funnel", "Explain how SEO ranking works",
                 "Choose between organic and paid channels", "Calculate CTR, conversion rate, CAC and ROI"],
    "modules": [
        ("Marketing foundations", [
            L("The marketing funnel", "article", 8, ["funnel"], """
The **marketing funnel** describes the journey from first hearing about a business to becoming a loyal customer. A common version has four stages:

1. **Awareness** - people discover you (ads, search, social posts).
2. **Consideration** - they compare options (reviews, product pages, emails).
3. **Conversion** - they take the action you want, such as buying or signing up.
4. **Retention** - they come back and recommend you.

Each stage is smaller than the one before, which is why it's drawn as a funnel. Different content serves different stages: a short video builds awareness, while a pricing comparison helps someone who is already considering.

## Example
A coffee subscription brand runs Instagram reels (awareness), publishes "how to choose beans" guides (consideration), offers a first-bag discount (conversion), and sends brewing tips to subscribers (retention).

## Key points
- Four stages: awareness, consideration, conversion, retention.
- Fewer people reach each later stage.
- Match content to the stage the audience is in.
"""),
            L("Know your audience", "article", 7, ["audience"], """
Good marketing starts with a clear picture of **who** you're talking to. A **buyer persona** is a short profile of a typical customer: their goals, problems, where they spend time online and what makes them trust a brand.

Personas are built from real evidence - customer interviews, surveys, website analytics and support conversations - not guesses.

**Segmentation** splits a market into groups with shared needs (for example by age, location, job role or behaviour) so you can tailor the message to each group.

## Example
"Busy Priya, 34, project manager, wants healthy lunches but has 20 minutes to cook. Scrolls Instagram on her commute. Trusts recipes with real reviews." A meal-kit brand would show Priya quick recipes and customer ratings, not long cooking tutorials.

## Key points
- Personas describe real customer goals and problems.
- Build them from data, not assumptions.
- Segmentation lets you tailor messages to groups.
"""),
            L("Quiz: foundations", "quiz", 5, ["funnel", "audience"], "Check your understanding of funnels and audiences.", quiz=[
                C("Which funnel stage is about people comparing options?", ["Awareness", "Consideration", "Conversion", "Retention"], 1, "funnel",
                  "Consideration is where people weigh up options before acting."),
                C("A loyalty email to existing customers mainly supports which stage?", ["Awareness", "Consideration", "Conversion", "Retention"], 3, "funnel",
                  "Retention is about bringing existing customers back."),
                C("What should a buyer persona be based on?", ["The founder's opinions", "Real customer research and data", "Competitors' logos", "Random demographics"], 1, "audience",
                  "Personas are only useful when built from real evidence."),
            ]),
        ]),
        ("Channels", [
            L("Search engine optimisation (SEO)", "article", 10, ["seo"], """
**SEO** is improving your website so it appears higher in unpaid (organic) search results. Search engines rank pages using three broad signals:

- **Relevance** - does the page genuinely answer what the person searched for? Use the words your audience uses (keywords) in titles, headings and content.
- **Authority** - do other trustworthy sites link to you? These links are called **backlinks**.
- **Experience** - is the page fast, mobile-friendly and easy to use?

SEO takes months to build but keeps delivering traffic without paying per click. Avoid "keyword stuffing" - repeating words unnaturally hurts rankings.

## Example
A bakery wants to rank for "gluten free birthday cake Leeds". It writes a helpful page with that title, real photos, prices and FAQs, gets listed on local food blogs (backlinks), and makes sure the page loads quickly on phones.

## Key points
- SEO targets organic (unpaid) search results.
- Ranking signals: relevance, authority (backlinks), experience.
- Results are slow to build but long-lasting.
"""),
            L("Social media and paid ads", "article", 9, ["paid-vs-organic"], """
**Organic social** means posting content to your own followers for free. It builds community and trust, but reach is limited.

**Paid advertising** (search ads, social ads, display ads) puts your message in front of a chosen audience immediately. You usually pay **per click (CPC)** or **per thousand impressions (CPM)**. Paid ads are fast and precisely targeted, but traffic stops when the budget stops.

Most businesses combine both: organic content to build trust, paid ads to reach new people and test messages quickly.

## Example
A new fitness app spends £500 on social ads targeted at 25-40 year olds interested in running, to get its first 1,000 downloads quickly, while posting free training tips every day to build a following.

## Key points
- Organic = free reach to your own audience; slow but builds trust.
- Paid = immediate, targeted reach; stops when spending stops.
- CPC = cost per click; CPM = cost per thousand impressions.
"""),
            L("Quiz: channels", "quiz", 5, ["seo", "paid-vs-organic"], "Test your channel knowledge.", quiz=[
                C("Links from other websites to yours are called…", ["Keywords", "Backlinks", "Impressions", "Cookies"], 1, "seo",
                  "Backlinks signal authority to search engines."),
                C("Which is a disadvantage of paid ads?", ["They are slow to start", "Traffic stops when budget stops", "They can't be targeted", "They don't appear in search"], 1, "paid-vs-organic",
                  "Paid traffic depends on continued spend."),
                C("What does CPM measure?", ["Cost per click", "Cost per thousand impressions", "Customers per month", "Clicks per minute"], 1, "paid-vs-organic",
                  "M is the Roman numeral for thousand: cost per mille."),
            ]),
        ]),
        ("Measuring success", [
            L("Key marketing metrics", "article", 12, ["ctr", "conversion-rate", "cac", "roi"], """
Marketing decisions should be driven by numbers. Four metrics matter most:

**Click-through rate (CTR)** = clicks ÷ impressions × 100. If an ad is shown 2,000 times and clicked 50 times, CTR = 50 ÷ 2,000 × 100 = **2.5%**.

**Conversion rate** = conversions ÷ visitors × 100. If 400 people visit a page and 12 buy, the conversion rate is **3%**.

**Customer acquisition cost (CAC)** = marketing spend ÷ new customers. Spending £600 to win 20 customers gives a CAC of **£30**.

**Return on investment (ROI)** = (revenue − cost) ÷ cost × 100. Earning £1,500 from a £500 campaign gives ROI = 1,000 ÷ 500 × 100 = **200%**.

## Example
Campaign A: £300 spend, 10 customers → CAC £30. Campaign B: £300 spend, 25 customers → CAC £12. Campaign B wins customers far more cheaply, so shift budget towards it.

## Key points
- CTR = clicks ÷ impressions × 100.
- Conversion rate = conversions ÷ visitors × 100.
- CAC = spend ÷ new customers.
- ROI = (revenue − cost) ÷ cost × 100.
"""),
            L("Quiz: marketing metrics", "quiz", 8, ["ctr", "conversion-rate", "cac", "roi"], "Use the formulas. Give numbers only (no % or £ needed).", quiz=[
                S("An ad gets 5,000 impressions and 100 clicks. What is the CTR in %?", ["2"], "ctr",
                  "CTR = 100 ÷ 5,000 × 100 = 2%.", tolerance=0.01),
                S("800 people visit a landing page and 24 sign up. What is the conversion rate in %?", ["3"], "conversion-rate",
                  "24 ÷ 800 × 100 = 3%.", tolerance=0.01),
                S("You spend £900 and gain 30 new customers. What is the CAC in £?", ["30"], "cac",
                  "CAC = 900 ÷ 30 = £30.", tolerance=0.01),
                S("A campaign costs £400 and brings in £1,000 revenue. What is the ROI in %?", ["150"], "roi",
                  "ROI = (1,000 − 400) ÷ 400 × 100 = 150%.", tolerance=0.01),
            ]),
            L("Assignment: plan a mini campaign", "assignment", 30, ["funnel", "audience", "paid-vs-organic", "roi"], """
Plan a one-month campaign for a business of your choice (real or imaginary). In 200-400 words, cover:

- Your **target audience** or persona.
- Which **channels** you'll use and why (organic, paid or both).
- Content for at least two **funnel** stages.
- The **metrics** you'll track and what result would count as success (e.g. a target CAC or ROI).
""", rubric=[
                {"criterion": "Defines a target audience", "keywords": ["audience", "persona", "customer"], "tip": "Describe who you're targeting and what they care about."},
                {"criterion": "Chooses and justifies channels", "keywords": ["seo", "social", "ads", "paid", "organic", "email"], "tip": "Name your channels and explain why they suit your audience."},
                {"criterion": "Covers funnel stages", "keywords": ["awareness", "consideration", "conversion", "retention"], "tip": "Show content for at least two funnel stages."},
                {"criterion": "Sets measurable metrics", "keywords": ["ctr", "conversion", "cac", "roi", "%"], "tip": "Pick metrics and a target number that would mean success."},
            ]),
        ]),
    ],
}

EXCEL = {
    "slug": "data-analysis-with-excel", "title": "Data Analysis with Excel",
    "subtitle": "Turn spreadsheets into answers",
    "description": "Learn the spreadsheet skills employers ask for: clean data, write formulas, look things up, summarise thousands of rows with pivot tables and present results with charts.",
    "category": "Data", "level": "Beginner", "colour": "#16a34a", "icon": "📊",
    "outcomes": ["Navigate cells, ranges and references", "Write SUM, AVERAGE, IF and COUNTIF formulas",
                 "Look up values with XLOOKUP", "Summarise data with pivot tables", "Choose the right chart"],
    "modules": [
        ("Spreadsheet essentials", [
            L("Cells, ranges and references", "article", 8, ["references"], """
A spreadsheet is a grid. Each **cell** has an address made of its column letter and row number, like **B3**. A **range** is a block of cells written with a colon: **A1:A10** means A1 down to A10.

Formulas refer to cells instead of typing numbers, so results update automatically when the data changes.

When you copy a formula, Excel adjusts the references - this is a **relative reference** (A1 becomes A2 when copied down). To lock a reference so it doesn't move, add dollar signs: **$A$1** is an **absolute reference**. $A1 locks only the column; A$1 locks only the row.

## Example
Prices are in B2:B10 and a VAT rate of 20% is in E1. In C2 write `=B2*$E$1` and copy it down. B2 changes to B3, B4… but $E$1 always points at the VAT rate.

## Key points
- Cells are addressed by column + row (B3).
- Ranges use a colon (A1:A10).
- Relative references move when copied; absolute ($A$1) do not.
"""),
            L("Essential formulas", "article", 12, ["formulas", "if-function"], """
Every formula starts with **=**. The most used functions:

- `=SUM(B2:B10)` adds up a range.
- `=AVERAGE(B2:B10)` finds the mean.
- `=MIN(...)` and `=MAX(...)` find the smallest and largest values.
- `=COUNT(B2:B10)` counts cells containing numbers; `=COUNTIF(C2:C50,"London")` counts cells matching a condition.
- `=IF(condition, value_if_true, value_if_false)` makes a decision.

## Example
Sales are in column B. In C2: `=IF(B2>=1000,"Target met","Below target")`. Copy it down to label every row. Then `=COUNTIF(C2:C50,"Target met")` tells you how many reps hit target.

## Key points
- Formulas begin with =.
- SUM, AVERAGE, MIN, MAX summarise ranges.
- COUNTIF counts cells matching a condition.
- IF returns one value when a condition is true and another when false.
"""),
            L("Quiz: essentials", "quiz", 6, ["references", "formulas", "if-function"], "Check your spreadsheet basics.", quiz=[
                C("Which reference stays fixed when a formula is copied?", ["A1", "$A$1", "A:A", "#A1"], 1, "references",
                  "Dollar signs lock both the column and the row."),
                S("Cells A1:A4 contain 2, 4, 6 and 8. What does =AVERAGE(A1:A4) return?", ["5"], "formulas",
                  "(2 + 4 + 6 + 8) ÷ 4 = 20 ÷ 4 = 5.", tolerance=0.001),
                C("What does =IF(B2>50,\"Pass\",\"Retry\") return when B2 is 50?", ["Pass", "Retry", "50", "An error"], 1, "if-function",
                  "50 is not greater than 50, so the false value \"Retry\" is returned."),
                C("Which function counts cells that match a condition?", ["SUM", "COUNT", "COUNTIF", "MAX"], 2, "formulas",
                  "COUNTIF(range, criteria) counts matching cells."),
            ]),
        ]),
        ("Analysing data", [
            L("Looking up values with XLOOKUP", "article", 10, ["lookup"], """
**XLOOKUP** finds a value in one column and returns the matching value from another:

`=XLOOKUP(lookup_value, lookup_array, return_array, [if_not_found])`

It replaces the older **VLOOKUP**, which only searches the first column of a table and breaks when columns are inserted. XLOOKUP can look left or right and lets you set a friendly message when nothing matches.

## Example
Product codes are in A2:A200 and prices in C2:C200. To find the price of the code in F2:
`=XLOOKUP(F2, A2:A200, C2:C200, "Not found")`

## Key points
- XLOOKUP searches one range and returns from another.
- It's more flexible than VLOOKUP.
- The optional 4th argument handles missing values.
"""),
            L("Pivot tables", "article", 12, ["pivot-tables"], """
A **pivot table** summarises thousands of rows in seconds without writing formulas. Select your data, choose **Insert → PivotTable**, then drag fields into four areas:

- **Rows** - the categories down the side (e.g. Region).
- **Columns** - categories across the top (e.g. Month).
- **Values** - the numbers to summarise (e.g. Sum of Sales).
- **Filters** - limit what's included (e.g. one product line).

Your data must be a clean table: one header row, no blank rows, one type of value per column.

## Example
From 5,000 rows of orders, drag Region to Rows and Sales to Values to see total sales per region instantly. Drag Month to Columns to see each region's monthly trend.

## Key points
- Pivot tables summarise large data without formulas.
- Four areas: Rows, Columns, Values, Filters.
- Source data must be a clean table.
"""),
            L("Choosing the right chart", "article", 7, ["charts"], """
The right chart makes the message obvious:

- **Column / bar chart** - compare categories (sales by region).
- **Line chart** - show change over time (monthly revenue).
- **Pie chart** - parts of a whole, only with a few categories that add to 100%.
- **Scatter chart** - relationship between two numbers (ad spend vs sales).

Give every chart a clear title that states the takeaway, label axes, and avoid 3D effects that distort values.

## Example
To show revenue growing over 12 months, use a line chart titled "Revenue grew 40% this year" - not a pie chart.

## Key points
- Bars compare categories; lines show trends over time.
- Pies only for a few parts of a whole.
- Scatter shows relationships between two variables.
"""),
            L("Quiz: analysis", "quiz", 6, ["lookup", "pivot-tables", "charts"], "Check your analysis skills.", quiz=[
                C("Which pivot table area holds the numbers you want to summarise?", ["Rows", "Columns", "Values", "Filters"], 2, "pivot-tables",
                  "Values is where Sum/Count/Average of a field go."),
                C("Best chart for showing monthly website visits over a year?", ["Pie", "Line", "Scatter", "Doughnut"], 1, "charts",
                  "Line charts show change over time."),
                C("What advantage does XLOOKUP have over VLOOKUP?", ["It only works on numbers", "It can return values from columns to the left", "It needs no lookup value", "It is only for dates"], 1, "lookup",
                  "VLOOKUP can only return columns to the right of the first column."),
            ]),
        ]),
    ],
}

UX = {
    "slug": "ui-ux-design-basics", "title": "UI/UX Design Basics",
    "subtitle": "Design products people find easy and enjoyable",
    "description": "Discover how designers understand users, sketch ideas, build wireframes and test them - plus the visual principles that make interfaces clear.",
    "category": "Design", "level": "Beginner", "colour": "#ea580c", "icon": "🎨",
    "outcomes": ["Apply the design thinking process", "Plan simple user research",
                 "Create low-fidelity wireframes", "Use visual hierarchy", "Run a usability test"],
    "modules": [
        ("Understanding users", [
            L("UX vs UI and design thinking", "article", 8, ["ux-vs-ui", "design-thinking"], """
**UX (user experience)** is how the whole product feels to use - is it useful, easy and pleasant? **UI (user interface)** is the visual and interactive layer - buttons, colours, typography, layout. Good UI is part of good UX, but UX also includes things like how fast a task can be completed.

**Design thinking** is a five-stage, repeatable process:
1. **Empathise** - understand users' needs.
2. **Define** - write a clear problem statement.
3. **Ideate** - generate many possible solutions.
4. **Prototype** - build quick, cheap versions.
5. **Test** - try them with real users and learn.

It's a loop: testing often sends you back to an earlier stage.

## Example
A bank notices people abandon its loan form. Designers interview users (empathise), define "applicants don't know which documents they need", sketch a checklist screen (ideate, prototype) and test it with five customers.

## Key points
- UX = the overall experience; UI = the interface layer.
- Design thinking: empathise, define, ideate, prototype, test.
- The process repeats based on what you learn.
"""),
            L("User research methods", "article", 9, ["user-research"], """
Research stops you designing for yourself. Common methods:

- **Interviews** - one-to-one conversations exploring needs and frustrations (qualitative: the *why*).
- **Surveys** - many people answering the same questions (quantitative: the *how many*).
- **Observation** - watching people use a product in context.
- **Analytics** - data on what people actually do on a site or app.

Ask open, neutral questions ("Tell me about the last time you…") rather than leading ones ("Wouldn't it be great if…?"). People are better at describing past behaviour than predicting future behaviour.

## Example
Instead of asking "Would you use a recipe-sharing feature?", ask "How did you choose what to cook last week?" - you learn what people really do.

## Key points
- Interviews explain why; surveys measure how many.
- Use open, non-leading questions.
- Ask about past behaviour, not hypothetical futures.
"""),
            L("Quiz: understanding users", "quiz", 5, ["ux-vs-ui", "design-thinking", "user-research"], "Check what you've learned about users.", quiz=[
                C("Which design thinking stage comes straight after Empathise?", ["Ideate", "Define", "Test", "Prototype"], 1, "design-thinking",
                  "Empathise → Define → Ideate → Prototype → Test."),
                C("Which is the best interview question?", ["Wouldn't you love a dark mode?", "Tell me about the last time you booked a train.", "Do you agree our app is easy?", "Would you pay £5 for this?"], 1, "user-research",
                  "Open questions about past behaviour avoid leading the participant."),
                C("Choosing button colours and fonts is mainly…", ["UX research", "UI design", "Analytics", "Project management"], 1, "ux-vs-ui",
                  "Visual elements like colour and typography are UI."),
            ]),
        ]),
        ("Designing and testing", [
            L("Wireframes and visual hierarchy", "article", 10, ["wireframes", "visual-hierarchy"], """
A **wireframe** is a simple layout sketch - boxes and labels, no colours or images - showing what goes where on a screen. Low-fidelity wireframes are fast to change, so you can explore many ideas before committing.

**Visual hierarchy** guides the eye to what matters most first. Designers create it with:
- **Size** - bigger elements are seen first.
- **Contrast and colour** - a bold button stands out from grey text.
- **Position** - people scan from the top-left in many languages.
- **Spacing** - white space groups related items and separates others.

Each screen should have one clear **primary action**.

## Example
A checkout page: large "Pay now" button in a strong colour (primary action), smaller "Edit basket" link (secondary), order summary grouped together with clear spacing.

## Key points
- Wireframes are quick, low-detail layout sketches.
- Hierarchy uses size, contrast, position and spacing.
- One clear primary action per screen.
"""),
            L("Usability testing", "article", 8, ["usability-testing"], """
In a **usability test**, real users try to complete realistic tasks with your design while you observe. You learn where they hesitate, misunderstand or fail.

Tips:
- Give tasks, not instructions: "Buy a size 8 trainer" rather than "Click the shop button".
- Ask people to **think aloud**.
- Don't help or defend the design - note what happens.
- Testing with about **five users** typically reveals most of the major problems; then fix and test again.

## Example
Three of five testers couldn't find the delivery options because they were hidden below the fold. The team moved them above the "Pay" button and re-tested - everyone found them.

## Key points
- Watch real users attempt realistic tasks.
- Use think-aloud and don't intervene.
- Small rounds (~5 users) repeated often find most issues.
"""),
            L("Quiz: designing and testing", "quiz", 5, ["wireframes", "visual-hierarchy", "usability-testing"], "Check your design and testing knowledge.", quiz=[
                C("What is a low-fidelity wireframe?", ["A finished, coloured mock-up", "A quick layout sketch without visual detail", "A survey", "A piece of code"], 1, "wireframes",
                  "Low-fi wireframes are simple boxes and labels."),
                C("Which technique does NOT create visual hierarchy?", ["Size", "Contrast", "Spacing", "Hiding the main button"], 3, "visual-hierarchy",
                  "Hierarchy makes important items more visible, not less."),
                S("Roughly how many users are typically enough to find most major usability issues in one round?", ["5", "five"], "usability-testing",
                  "Around five users per round, repeated after fixes.", tolerance=1),
            ]),
        ]),
    ],
}

DRAFT_PM = {
    "slug": "project-management-essentials", "title": "Project Management Essentials",
    "subtitle": "Deliver projects on time and on budget",
    "description": "Scope, plan, schedule and deliver projects with confidence. (Draft - in production by the content team.)",
    "category": "Business", "level": "Beginner", "colour": "#7c3aed", "icon": "🗂️",
    "outcomes": ["Define project scope", "Build a schedule", "Manage risks and stakeholders"],
    "status": "draft",
    "modules": [
        ("Project basics", [
            L("What makes a project?", "article", 6, ["project-basics"], """
A **project** is temporary work with a clear goal, a start and an end. It's constrained by the **triple constraint**: scope (what), time (when) and cost (how much). Changing one affects the others.

## Key points
- Projects are temporary with a defined goal.
- Scope, time and cost are linked.
"""),
        ]),
    ],
}

COURSES = [PYTHON, MARKETING, EXCEL, UX, DRAFT_PM]
CATEGORIES = ["Programming", "Marketing", "Data", "Design", "Business"]
