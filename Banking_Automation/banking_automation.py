"""
Banking Automation System
-------------------------
A simple console-based banking application.

Features:
  - Create account (with PIN)
  - Login / Logout
  - Deposit, Withdraw, Transfer
  - Balance enquiry
  - Mini statement (transaction history)
  - Change PIN
  - Data saved permanently in bank_data.json

Run:  python banking_automation.py
"""

import hashlib
import json
import os
import random
from datetime import datetime
from getpass import getpass

DATA_FILE = "bank_data.json"
MIN_BALANCE = 0.0          # minimum balance that must remain after withdrawal
MAX_PIN_ATTEMPTS = 3


# ---------------------------------------------------------------- helpers
def hash_pin(pin: str, salt: str) -> str:
    return hashlib.sha256((salt + pin).encode()).hexdigest()


def now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def read_amount(prompt: str) -> float:
    """Keep asking until a valid positive number is entered."""
    while True:
        try:
            value = float(input(prompt))
            if value <= 0:
                print("  Amount must be greater than zero.")
                continue
            return round(value, 2)
        except ValueError:
            print("  Please enter a valid number.")


def read_pin(prompt: str = "Enter 4-digit PIN: ") -> str:
    try:
        return getpass(prompt)
    except Exception:          # some IDE consoles don't support getpass
        return input(prompt)


def valid_pin(pin: str) -> bool:
    return pin.isdigit() and len(pin) == 4


# ---------------------------------------------------------------- model
class Account:
    def __init__(self, acc_no, name, pin_hash, salt, balance=0.0, history=None):
        self.acc_no = acc_no
        self.name = name
        self.pin_hash = pin_hash
        self.salt = salt
        self.balance = balance
        self.history = history or []

    def check_pin(self, pin: str) -> bool:
        return hash_pin(pin, self.salt) == self.pin_hash

    def set_pin(self, pin: str):
        self.salt = os.urandom(8).hex()
        self.pin_hash = hash_pin(pin, self.salt)

    def log(self, kind: str, amount: float, note: str = ""):
        self.history.append({
            "time": now(),
            "type": kind,
            "amount": amount,
            "balance": round(self.balance, 2),
            "note": note,
        })

    def to_dict(self):
        return self.__dict__.copy()

    @staticmethod
    def from_dict(d):
        return Account(**d)


class Bank:
    def __init__(self, path=DATA_FILE):
        self.path = path
        self.accounts = {}
        self.load()

    # ---- persistence
    def load(self):
        if os.path.exists(self.path):
            try:
                with open(self.path, "r") as f:
                    raw = json.load(f)
                self.accounts = {k: Account.from_dict(v) for k, v in raw.items()}
            except (json.JSONDecodeError, TypeError):
                print("Warning: data file corrupted. Starting fresh.")
                self.accounts = {}

    def save(self):
        with open(self.path, "w") as f:
            json.dump({k: a.to_dict() for k, a in self.accounts.items()}, f, indent=2)

    # ---- operations
    def new_acc_no(self) -> str:
        while True:
            no = str(random.randint(10**9, 10**10 - 1))
            if no not in self.accounts:
                return no

    def create_account(self, name, pin, opening_balance=0.0) -> Account:
        acc_no = self.new_acc_no()
        acc = Account(acc_no, name, "", "")
        acc.set_pin(pin)
        acc.balance = opening_balance
        acc.log("OPEN", opening_balance, "Account opened")
        self.accounts[acc_no] = acc
        self.save()
        return acc

    def login(self, acc_no, pin):
        acc = self.accounts.get(acc_no)
        return acc if acc and acc.check_pin(pin) else None

    def deposit(self, acc, amount):
        acc.balance += amount
        acc.log("DEPOSIT", amount)
        self.save()

    def withdraw(self, acc, amount):
        if acc.balance - amount < MIN_BALANCE:
            return False
        acc.balance -= amount
        acc.log("WITHDRAW", amount)
        self.save()
        return True

    def transfer(self, src, dest_no, amount):
        dest = self.accounts.get(dest_no)
        if dest is None:
            return "Destination account not found."
        if dest is src:
            return "Cannot transfer to your own account."
        if src.balance - amount < MIN_BALANCE:
            return "Insufficient balance."
        src.balance -= amount
        dest.balance += amount
        src.log("TRANSFER OUT", amount, f"To {dest_no}")
        dest.log("TRANSFER IN", amount, f"From {src.acc_no}")
        self.save()
        return None


# ---------------------------------------------------------------- UI
def create_account_flow(bank: Bank):
    print("\n--- Create New Account ---")
    name = input("Full name: ").strip()
    if not name:
        print("Name cannot be empty.")
        return
    pin = read_pin("Set a 4-digit PIN: ")
    if not valid_pin(pin):
        print("PIN must be exactly 4 digits.")
        return
    if pin != read_pin("Confirm PIN: "):
        print("PINs do not match.")
        return
    try:
        opening = float(input("Opening deposit (0 for none): ") or 0)
        if opening < 0:
            raise ValueError
    except ValueError:
        print("Invalid amount.")
        return
    acc = bank.create_account(name, pin, round(opening, 2))
    print(f"\nAccount created successfully!")
    print(f"  Account Number : {acc.acc_no}   <-- note this down")
    print(f"  Holder         : {acc.name}")
    print(f"  Balance        : {acc.balance:.2f}")


def login_flow(bank: Bank):
    print("\n--- Login ---")
    acc_no = input("Account number: ").strip()
    if acc_no not in bank.accounts:
        print("Account not found.")
        return None
    for attempt in range(1, MAX_PIN_ATTEMPTS + 1):
        acc = bank.login(acc_no, read_pin())
        if acc:
            print(f"\nWelcome, {acc.name}!")
            return acc
        print(f"  Wrong PIN ({attempt}/{MAX_PIN_ATTEMPTS})")
    print("Too many failed attempts. Returning to main menu.")
    return None


def show_statement(acc: Account, last_n=10):
    print(f"\n--- Mini Statement (last {last_n}) ---")
    print(f"{'Date/Time':<20}{'Type':<14}{'Amount':>12}{'Balance':>12}  Note")
    print("-" * 72)
    for t in acc.history[-last_n:]:
        print(f"{t['time']:<20}{t['type']:<14}{t['amount']:>12.2f}"
              f"{t['balance']:>12.2f}  {t['note']}")


def account_menu(bank: Bank, acc: Account):
    while True:
        print(f"""
===== Account Menu ({acc.acc_no}) =====
1. Check Balance
2. Deposit
3. Withdraw
4. Transfer Money
5. Mini Statement
6. Change PIN
7. Logout""")
        choice = input("Choose: ").strip()

        if choice == "1":
            print(f"\nCurrent balance: {acc.balance:.2f}")

        elif choice == "2":
            amt = read_amount("Deposit amount: ")
            bank.deposit(acc, amt)
            print(f"Deposited {amt:.2f}. New balance: {acc.balance:.2f}")

        elif choice == "3":
            amt = read_amount("Withdraw amount: ")
            if bank.withdraw(acc, amt):
                print(f"Withdrawn {amt:.2f}. New balance: {acc.balance:.2f}")
            else:
                print("Insufficient balance.")

        elif choice == "4":
            dest = input("Destination account number: ").strip()
            amt = read_amount("Transfer amount: ")
            error = bank.transfer(acc, dest, amt)
            print(error or f"Transferred {amt:.2f} to {dest}. "
                           f"New balance: {acc.balance:.2f}")

        elif choice == "5":
            show_statement(acc)

        elif choice == "6":
            if not acc.check_pin(read_pin("Current PIN: ")):
                print("Incorrect PIN.")
                continue
            new = read_pin("New 4-digit PIN: ")
            if not valid_pin(new):
                print("PIN must be exactly 4 digits.")
                continue
            acc.set_pin(new)
            bank.save()
            print("PIN changed successfully.")

        elif choice == "7":
            print("Logged out.")
            return
        else:
            print("Invalid choice.")


def main():
    bank = Bank()
    while True:
        print("""
##############################
#    BANKING AUTOMATION      #
##############################
1. Create Account
2. Login
3. Exit""")
        choice = input("Choose: ").strip()
        if choice == "1":
            create_account_flow(bank)
        elif choice == "2":
            acc = login_flow(bank)
            if acc:
                account_menu(bank, acc)
        elif choice == "3":
            print("Thank you for banking with us. Goodbye!")
            break
        else:
            print("Invalid choice.")


if __name__ == "__main__":
    main()
