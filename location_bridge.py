"""Reception plan editor using the shared library's DAB block validator."""
import json
from pathlib import Path
from PySide6.QtCore import Property, Signal, Slot
from discovery_bridge import DiscoveryBridge


class LocationBridge(DiscoveryBridge):
    plansChanged = Signal()

    def __init__(self,directory,parent=None,*,process_command=None):
        command=process_command or ['php',str(Path(__file__).with_name('backend')/'locations.php'),str(directory)]
        super().__init__(directory,parent,process_command=command)
        self.changed.connect(self.plansChanged.emit)
        self._revision=''
        self._selected='__full_band__'
        self._mutation=False

    selected = Property(str,lambda self:self._selected,notify=plansChanged)

    @Slot()
    def open(self):
        if not self._busy:self._start({'action':'list'})

    def _start(self,request):
        self._mutation=request['action']!='list'
        request=dict(request,revision=self._revision)
        super()._start(request)
        self._saving=self._mutation
        self._message='Updating reception locations…' if self._mutation else 'Loading reception locations…'
        self.changed.emit()

    @Slot(str,'QVariantList',str)
    def savePlan(self,name,channels,original):
        if not self._busy:
            self._start({'action':'save','name':name,'channels':channels,'original':original or None})

    @Slot(str)
    def deletePlan(self,name):
        if not self._busy:self._start({'action':'delete','name':name})

    @Slot(str)
    def selectPlan(self,name):
        if not self._busy:self._start({'action':'select','name':name})

    def _finished(self,code,status):
        if not self._busy:return
        self._read()
        if not self._busy:return
        self._timer.stop();self._busy=self._saving=False
        success=False
        try:
            message=json.loads(self._output)
            if not isinstance(message,dict):raise ValueError()
            if code==0 and message.get('type')=='locations':
                items=message['items']
                if not isinstance(items,list) or len(items)>50 or any(not isinstance(i,dict)
                    or not isinstance(i.get('key'),str) or not isinstance(i.get('name'),str)
                    or not isinstance(i.get('channels'),list) or len(i['channels'])>38
                    or any(not isinstance(c,str) for c in i['channels'])
                    or not isinstance(i.get('detail'),str) for i in items):
                    raise ValueError()
                if (not isinstance(message.get('revision'),str) or not isinstance(message.get('selected'),str)
                    or not isinstance(message.get('message'),str)):raise ValueError()
                self._items=items;self._revision=message['revision'];self._selected=message['selected']
                self._message=message['message'];success=self._mutation
            elif message.get('type')=='error' and isinstance(message.get('message'),str):
                self._message=message['message']
            else:raise ValueError()
        except (ValueError,KeyError,TypeError,UnicodeError):
            self._message='Invalid location response. Reopen Reception locations to check saved settings.'
        self.changed.emit()
        if success:self.saved.emit()
