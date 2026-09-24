import trick

sdk_test.model.value = 12.5
if sdk_test.model.value != 12.5:
    raise RuntimeError("SDK model binding failed")
with open("sdk-input-ran", "w") as marker:
    marker.write("12.5\n")
trick.exec_set_terminate_time(0.01)
