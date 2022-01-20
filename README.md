# In-Vehicle Recorder

Multi-purpose in-vehicle recorder for Raspberry Pi

## Setup Your Raspberry Pi

### 

工場出荷直後の Raspberry Pi を外部から ssh で接続できるように手作業で設定する必要があります。

- `rpi-update` によるファームウェアの更新。
- `apt update && apt upgrade` によるシステムやライブラリの更新。
- `raspi-config` の実行。
  - ssh 接続の許可 (必須)。
  - WiFi、パスワード、ホスト名、ロケール、タイムゾーンといったシステム固有の基本設定 (任意)。

### Run Ansible Playbook

ターゲットの Raspberry Pi の接続先情報で `hosts` を更新します。

```
$ ansible-playbook -i hosts site.yml
```