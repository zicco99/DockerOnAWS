const connectToDatabase = () => {
    const dummyPromise = new Promise((resolve, reject) => {
        setTimeout(() => {
            resolve("Database is connected");
        }, 1000);
    });
    return dummyPromise;
}

export default connectToDatabase;