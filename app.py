def get_img(entry):
    link = entry.get('link','')
    # Khabar wali site ka live screenshot hi photo ban jayega
    return f"https://image.thum.io/get/width/600/crop/400/noanimate/{link}"
