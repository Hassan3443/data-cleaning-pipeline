"""Generate a realistic messy sales dataset for the cleaning pipeline demo.

The dataset deliberately contains the data-quality issues the pipeline fixes:
duplicates, mixed date formats, inconsistent category casing, missing values,
currency symbols inside numeric fields, and invalid negative quantities.
"""
import random
import csv
from datetime import date, timedelta

random.seed(42)

CATEGORIES = ["Electronics", "Clothing", "Home & Kitchen", "Books", "Sports"]
REGIONS = ["Cairo", "Alexandria", "Giza", "Mansoura", "Aswan"]
PAYMENTS = ["Credit Card", "Cash", "Mobile Wallet", "Bank Transfer"]
PRODUCTS = {
    "Electronics": ["Wireless Mouse", "Bluetooth Speaker", "USB-C Hub", "Webcam HD", "Keyboard"],
    "Clothing": ["T-Shirt", "Jeans", "Hoodie", "Sneakers", "Cap"],
    "Home & Kitchen": ["Coffee Maker", "Blender", "Cookware Set", "Desk Lamp", "Air Fryer"],
    "Books": ["Python Handbook", "Data Science 101", "Novel", "Cookbook", "Biography"],
    "Sports": ["Yoga Mat", "Dumbbells", "Football", "Jump Rope", "Water Bottle"],
}
DATE_FORMATS = ["%Y-%m-%d", "%d/%m/%Y", "%m-%d-%Y", "%d %b %Y"]


def messy(value, kind):
    """Inject realistic messiness into a value."""
    r = random.random()
    if kind == "category":
        variants = [value, value.lower(), value.upper(), value + " ", value.replace(" & ", " and ")]
        return random.choice(variants)
    if kind == "region":
        variants = [value, value.lower(), " " + value, value.upper()]
        return random.choice(variants)
    if kind == "price":
        variants = [f"{value:.2f}", f"${value:.2f}", f"{value:,.2f} EGP", f"{value:.2f}"]
        return random.choice(variants)
    return value


def main():
    start = date(2025, 1, 1)
    rows = []
    for i in range(1, 1201):
        category = random.choice(CATEGORIES)
        order_date = start + timedelta(days=random.randint(0, 700))
        fmt = random.choice(DATE_FORMATS)
        quantity = random.randint(1, 5)
        price = round(random.uniform(50, 5000), 2)

        # Inject problems
        if random.random() < 0.03:
            quantity = -quantity  # invalid negative quantity
        customer = f"CUST-{random.randint(1, 400):04d}"
        if random.random() < 0.04:
            customer = ""  # missing customer id
        region = messy(random.choice(REGIONS), "region")
        if random.random() < 0.03:
            region = ""
        payment = random.choice(PAYMENTS)
        if random.random() < 0.03:
            payment = ""

        rows.append({
            "Order ID": f"ORD-{i:05d}",
            "Order Date": order_date.strftime(fmt),
            "Customer ID": customer,
            "Product Name": random.choice(PRODUCTS[category]),
            "Category": messy(category, "category"),
            "Region": region,
            "Quantity": quantity,
            "Unit Price": messy(price, "price"),
            "Payment Method": payment,
        })

    # Inject exact duplicates (~4%)
    dupes = random.sample(rows, 48)
    rows.extend(dupes)
    random.shuffle(rows)

    with open("data/raw/messy_sales.csv", "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    print(f"Wrote {len(rows)} messy rows to data/raw/messy_sales.csv")


if __name__ == "__main__":
    main()
