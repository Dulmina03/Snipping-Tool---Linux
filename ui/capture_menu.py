import tkinter as tk


class CaptureMenu:
    def __init__(self, root):
        self.root = root

        self.root.title("Capture")
        self.root.geometry("260x330")
        self.root.resizable(False, False)

        self.capture_mode = "selected_area"
        self.action = "screenshot"

        self.build_ui()

    def build_ui(self):
        title = tk.Label(
            self.root,
            text="Capture",
            font=("Sans", 18, "bold")
        )

        title.pack(
            pady=(15, 10)
        )

        # -------------------------
        # Capture mode
        # -------------------------

        mode_label = tk.Label(
            self.root,
            text="Capture Mode",
            font=("Sans", 10, "bold")
        )

        mode_label.pack(
            anchor="w",
            padx=20
        )

        self.mode_var = tk.StringVar(
            value="selected_area"
        )

        modes = [
            ("Full Screen", "full_screen"),
            ("Window", "window"),
            ("Selected Area", "selected_area"),
        ]

        for text, value in modes:

            radio = tk.Radiobutton(
                self.root,
                text=text,
                variable=self.mode_var,
                value=value,
                command=self.mode_changed
            )

            radio.pack(
                anchor="w",
                padx=30
            )

        # -------------------------
        # Action
        # -------------------------

        separator = tk.Frame(
            self.root,
            height=1,
            bg="gray"
        )

        separator.pack(
            fill="x",
            padx=20,
            pady=10
        )

        action_label = tk.Label(
            self.root,
            text="Action",
            font=("Sans", 10, "bold")
        )

        action_label.pack(
            anchor="w",
            padx=20
        )

        self.action_var = tk.StringVar(
            value="screenshot"
        )

        actions = [
            ("Screenshot", "screenshot"),
            ("Extract Text", "ocr"),
            ("Ask AI", "ai"),
        ]

        for text, value in actions:

            radio = tk.Radiobutton(
                self.root,
                text=text,
                variable=self.action_var,
                value=value,
                command=self.action_changed
            )

            radio.pack(
                anchor="w",
                padx=30
            )

        # -------------------------
        # Capture button
        # -------------------------

        self.capture_button = tk.Button(
            self.root,
            text="Capture",
            font=("Sans", 10, "bold"),
            command=self.capture
        )

        self.capture_button.pack(
            fill="x",
            padx=20,
            pady=(15, 10)
        )

    def mode_changed(self):
        self.capture_mode = self.mode_var.get()

        print(
            "Capture mode:",
            self.capture_mode
        )

    def action_changed(self):
        self.action = self.action_var.get()

        print(
            "Action:",
            self.action
        )

    def capture(self):

        self.capture_mode = self.mode_var.get()
        self.action = self.action_var.get()

        print()
        print("========== CAPTURE ==========")
        print("Mode:", self.capture_mode)
        print("Action:", self.action)
        print("=============================")
        print()

        self.root.destroy()


def main():

    root = tk.Tk()

    app = CaptureMenu(
        root
    )

    root.mainloop()


if __name__ == "__main__":
    main()
