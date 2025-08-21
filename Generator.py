import json
import os
import random
import string
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog

DB_FILENAME = 'user_db.json'

class UserManagerApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("XRay 实体用户管理系统")
        self.geometry("800x600")

        # 数据
        self.db_path = DB_FILENAME
        self.db = {"users": []}
        self.outlets = []

        # UI 元素
        self.user_listbox = tk.Listbox(self)
        self.user_listbox.pack(side=tk.LEFT, fill=tk.Y)
        self.user_listbox.bind('<<ListboxSelect>>', self.on_user_select)

        btn_frame = tk.Frame(self)
        btn_frame.pack(side=tk.TOP, fill=tk.X)
        tk.Button(btn_frame, text="加载出口(outbounds.json)", command=self.load_outbounds).pack(side=tk.LEFT)
        tk.Button(btn_frame, text="添加用户", command=self.add_user).pack(side=tk.LEFT)
        tk.Button(btn_frame, text="编辑用户", command=self.edit_user).pack(side=tk.LEFT)
        tk.Button(btn_frame, text="删除用户", command=self.delete_user).pack(side=tk.LEFT)
        tk.Button(btn_frame, text="删除无效出口", command=self.clean_invalid_outlets).pack(side=tk.LEFT)
        tk.Button(btn_frame, text="生成配置", command=self.generate_configs).pack(side=tk.LEFT)

        detail_frame = tk.Frame(self)
        detail_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)
        self.detail_text = tk.Text(detail_frame)
        self.detail_text.pack(fill=tk.BOTH, expand=True)

        self.load_db()
        self.refresh_user_list()

    def load_db(self):
        if os.path.exists(self.db_path):
            with open(self.db_path, 'r', encoding='utf-8') as f:
                self.db = json.load(f)
        else:
            self.db = {"users": []}

    def save_db(self):
        with open(self.db_path, 'w', encoding='utf-8') as f:
            json.dump(self.db, f, ensure_ascii=False, indent=2)

    def refresh_user_list(self):
        self.user_listbox.delete(0, tk.END)
        for user in self.db['users']:
            display = f"{user['username']} ({user['uuid']})"
            self.user_listbox.insert(tk.END, display)

    def on_user_select(self, event):
        sel = self.user_listbox.curselection()
        if not sel:
            return
        idx = sel[0]
        user = self.db['users'][idx]
        self.detail_text.delete('1.0', tk.END)
        self.detail_text.insert(tk.END, json.dumps(user, ensure_ascii=False, indent=2))

    def load_outbounds(self):
        path = filedialog.askopenfilename(title="选择 outbounds.json 文件", filetypes=[("JSON Files","*.json")])
        if not path:
            return
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        self.outlets = [o['tag'] for o in data.get('outbounds', []) if o.get('protocol') != 'blackhole']
        messagebox.showinfo("成功", f"加载到出口: {', '.join(self.outlets)}")

    def clean_invalid_outlets(self):
        if not self.outlets:
            messagebox.showwarning("错误", "请先加载出口列表！")
            return
        changed = False
        for user in self.db['users']:
            before = set(user['outlets'])
            user['outlets'] = [tag for tag in user['outlets'] if tag in self.outlets]
            if set(user['outlets']) != before:
                changed = True
        if changed:
            self.save_db()
            self.refresh_user_list()
            messagebox.showinfo("完成", "已删除所有无效出口。")
        else:
            messagebox.showinfo("提示", "未发现无效出口，无需更改。")

    def add_user(self):
        username = simpledialog.askstring("用户名", "请输入实体用户名（不包含后缀.local）：")
        if not username:
            return
        outlets = self.choose_outlets()
        if outlets is None:
            return
        uuid = ''.join(random.choices(string.ascii_lowercase + string.digits, k=20)) + '-'
        user = {"username": username, "uuid": uuid, "outlets": outlets}
        self.db['users'].append(user)
        self.save_db()
        self.refresh_user_list()

    def edit_user(self):
        sel = self.user_listbox.curselection()
        if not sel:
            return
        idx = sel[0]
        user = self.db['users'][idx]
        outlets = self.choose_outlets(prefill=user['outlets'])
        if outlets is None:
            return
        user['outlets'] = outlets
        self.save_db()
        self.on_user_select(None)

    def delete_user(self):
        sel = self.user_listbox.curselection()
        if not sel:
            return
        idx = sel[0]
        if messagebox.askyesno("确认", "删除选中用户？"):
            self.db['users'].pop(idx)
            self.save_db()
            self.refresh_user_list()
            self.detail_text.delete('1.0', tk.END)

    def choose_outlets(self, prefill=None):
        if not self.outlets:
            messagebox.showwarning("错误", "请先加载出口列表！")
            return None
        dialog = tk.Toplevel(self)
        dialog.title("选择出口")
        lb = tk.Listbox(dialog, selectmode=tk.MULTIPLE)
        lb.pack(fill=tk.BOTH, expand=True)
        for tag in self.outlets:
            lb.insert(tk.END, tag)
        if prefill:
            for i, tag in enumerate(self.outlets):
                if tag in prefill:
                    lb.selection_set(i)
        tk.Button(dialog, text="确定", command=lambda: (setattr(dialog, 'chosen', [self.outlets[i] for i in lb.curselection()]), dialog.destroy())).pack()
        self.wait_window(dialog)
        return getattr(dialog, 'chosen', None)

    def generate_configs(self):
        re_path = filedialog.askopenfilename(title="选择 01_inbound_RE.json", filetypes=[("JSON Files","*.json")])
        xh_path = filedialog.askopenfilename(title="选择 02_inbound_XH.json", filetypes=[("JSON Files","*.json")])
        dns_path = filedialog.askopenfilename(title="选择 03_dns.json", filetypes=[("JSON Files","*.json")])
        if not (re_path and xh_path and dns_path):
            return

        # 处理 RE (vless)
        with open(re_path, 'r', encoding='utf-8') as f:
            re_cfg = json.load(f)
        settings = re_cfg['inbounds'][0]['settings']
        clients_existing = settings.get('clients', [])
        # 提取 flow，若不存在则使用默认
        if clients_existing and 'flow' in clients_existing[0]:
            flow = clients_existing[0]['flow']
        else:
            flow = 'xtls-rprx-vision'
        clients_re = []
        for user in self.db['users']:
            for tag in user['outlets']:
                clients_re.append({
                    'id': user['uuid'] + tag,
                    'email': f"{tag}@{user['username']}.local",
                    'flow': flow
                })
        re_cfg['inbounds'][0]['settings']['clients'] = clients_re
        with open(re_path, 'w', encoding='utf-8') as f:
            json.dump(re_cfg, f, ensure_ascii=False, indent=2)

        # 处理 XH (xhttp)
        with open(xh_path, 'r', encoding='utf-8') as f:
            xh_cfg = json.load(f)
        clients_xh = []
        for user in self.db['users']:
            for tag in user['outlets']:
                clients_xh.append({
                    'id': user['uuid'] + tag,
                    'email': f"{tag}@{user['username']}.local"
                })
        xh_cfg['inbounds'][0]['settings']['clients'] = clients_xh
        with open(xh_path, 'w', encoding='utf-8') as f:
            json.dump(xh_cfg, f, ensure_ascii=False, indent=2)

        # 处理 DNS 路由：保留原有非 user/outboundTag 规则，
        # 并按 outletTag 聚合所有对应的实体用户 email
        with open(dns_path, 'r', encoding='utf-8') as f:
            dns_cfg = json.load(f)
        base_rules = [r for r in dns_cfg['routing']['rules'] if set(r.keys()) != {'user', 'outboundTag'}]
        mapping = {}
        for user in self.db['users']:
            for tag in user['outlets']:
                email = f"{tag}@{user['username']}.local"
                mapping.setdefault(tag, []).append(email)
        user_rules = []
        for tag, emails in mapping.items():
            user_rules.append({
                'user': emails,
                'outboundTag': tag
            })
        dns_cfg['routing']['rules'] = base_rules + user_rules
        with open(dns_path, 'w', encoding='utf-8') as f:
            json.dump(dns_cfg, f, ensure_ascii=False, indent=2)

        messagebox.showinfo("完成", "配置文件已根据实体用户数据库生成并覆盖相关部分。")

if __name__ == '__main__':
    app = UserManagerApp()
    app.mainloop()
